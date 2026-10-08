"""The Skill eval scores observed Codex traces, not source-text promises."""

import os

import pytest

from tools.cet6_skill_eval import score_trace


def _trace(command: str, reply: str, exit_code: int = 0):
    return [
        {"type": "item.completed", "item": {"type": "command_execution", "command": command,
                                           "exit_code": exit_code}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": reply}},
        {"type": "turn.completed"},
    ]


def test_unit_tests_do_not_enable_external_langsmith_tracing():
    assert os.environ.get("LANGSMITH_TRACING") == "false"
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"


def test_score_trace_accepts_observed_task_without_reference_leak():
    case = {"command": "tools.cet6_skill task 2024 12 1 translation",
            "forbid_command": ["tools.cet6_skill reference"],
            "reply_contains": ["北斗"], "reply_forbids": ["The successful development"]}
    assert score_trace(case, _trace("python -m tools.cet6_skill task 2024 12 1 translation",
                                    "题目涉及北斗卫星系统。")) == []


def test_score_trace_reports_missing_command_and_spoiler():
    case = {"command": "tools.cet6_skill task", "forbid_command": ["tools.cet6_skill reference"],
            "reply_forbids": ["The successful development"]}
    failed = score_trace(case, _trace("python -m tools.cet6_skill reference 2024 12 1 translation --confirm",
                                      "The successful development of Beidou"))
    assert "missing_command" in failed
    assert "forbidden_command" in failed
    assert "reply_leak" in failed


def test_score_trace_requires_correct_coordinates_in_tool_command():
    case = {"command": "tools.cet6_skill ask", "command_contains": ["2024年12月第1套第44题"]}
    failed = score_trace(case, _trace("python -m tools.cet6_skill ask '2024年12月第2套第44题'",
                                      "第44题答案：E"))
    assert failed == ["wrong_coordinates"]


def test_score_trace_accepts_markdown_bold_around_correct_answer_letter():
    case = {"reply_pattern": r"(?:答案|选)\s*[：:]*\s*E\b"}
    assert score_trace(case, _trace("python -m tools.cet6_skill ask '第44题'",
                                    "第44题选 **E**。")) == []


def test_score_trace_rejects_incomplete_and_failed_tool_run():
    case = {"command": "tools.cet6_skill progress"}
    assert "incomplete_trace" in score_trace(case, _trace("python -m tools.cet6_skill progress", "ok")[:-1])
    assert "tool_failed" in score_trace(case, _trace("python -m tools.cet6_skill progress", "ok", 1))


def test_score_trace_ignores_failed_environment_probe_when_skill_command_succeeds():
    case = {"command": "tools.cet6_skill task 2024 12 1 translation"}
    events = _trace("Get-ChildItem -Name .venv,venv", "probing", 1)[:-1]
    events += _trace("python -m tools.cet6_skill task 2024 12 1 translation", "北斗题目")
    assert score_trace(case, events) == []


def test_score_trace_ignores_a_recovered_progress_output_decode_failure():
    operation = "tools.cet6_skill progress"
    case = {"command": operation, "allow_recovered_actions": ["progress"]}
    failed_decode = _trace(
        "python -c \"subprocess.run(['-m','tools.cet6_skill','progress']); decode('utf-8')\"",
        "UnicodeDecodeError", 1,
    )[:-2]
    successful_retry = _trace(
        "python -c \"subprocess.run(['-m','tools.cet6_skill','progress']); decode('gbk')\"",
        "progress JSON",
    )
    initial_progress = _trace("python -m tools.cet6_skill progress", "progress JSON")[:-2]
    events = initial_progress + failed_decode + successful_retry

    assert score_trace(case, events) == []


def test_score_trace_does_not_treat_an_unrelated_success_as_progress_recovery():
    case = {"command": "tools.cet6_skill progress",
            "allow_recovered_actions": ["progress"]}
    failed_progress = _trace("python -m tools.cet6_skill progress", "decode failed", 1)[:-2]
    unrelated_success = _trace("python -m tools.cet6_skill history --section writing", "history")

    assert score_trace(case, failed_progress + unrelated_success) == ["tool_failed"]


def test_score_trace_negative_control_rejects_skill_tool_call():
    case = {"no_skill_command": True}
    assert score_trace(case, _trace("Get-Date", "今天是星期三")) == []
    assert "unexpected_skill_command" in score_trace(
        case, _trace("python -m tools.cet6_skill ask '第43题'", "A"))


def test_timeout_keeps_partial_codex_trace_for_diagnosis(tmp_path):
    import os
    import sys
    from tools import cet6_skill_eval

    trace = tmp_path / "partial.jsonl"
    command = [sys.executable, "-u", "-c",
               "import time; print('{\"type\":\"thread.started\"}', flush=True); time.sleep(10)"]
    assert cet6_skill_eval.capture_trace(command, trace, os.environ.copy(), timeout=0.5) is None
    assert trace.read_text(encoding="utf-8") == '{"type":"thread.started"}\n'


def test_eval_run_disables_external_tracing_and_isolates_learning_path(tmp_path, monkeypatch):
    import json
    from tools import cet6_skill_eval

    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "one", "prompt": "test"}]), encoding="utf-8")
    monkeypatch.setattr(cet6_skill_eval, "CASES_PATH", cases)

    def capture(_command, path, env, timeout):
        assert env["LANGSMITH_TRACING"] == "false"
        assert env["LANGCHAIN_TRACING_V2"] == "false"
        assert env["EXAM_TUTOR_LEARNING_PATH"] != str(tmp_path / "real_learning.jsonl")
        settings = [_command[index + 1] for index, token in enumerate(_command[:-1]) if token == "-c"]
        assert 'shell_environment_policy.set.LANGSMITH_TRACING="false"' in settings
        assert 'shell_environment_policy.set.LANGCHAIN_TRACING_V2="false"' in settings
        assert ('shell_environment_policy.set.EXAM_TUTOR_LEARNING_PATH='
                + json.dumps(env["EXAM_TUTOR_LEARNING_PATH"].replace("\\", "/"))) in settings
        assert timeout > 0
        path.write_text('{"type":"turn.completed"}\n', encoding="utf-8")
        return 0

    monkeypatch.setenv("EXAM_TUTOR_LEARNING_PATH", str(tmp_path / "real_learning.jsonl"))
    monkeypatch.setattr(cet6_skill_eval, "capture_trace", capture)
    assert cet6_skill_eval.main(["--run", "--trace-dir", str(tmp_path / "traces")]) == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows .cmd launch regression")
def test_eval_run_launches_cmd_shim_found_on_path(tmp_path, monkeypatch):
    import json
    from tools import cet6_skill_eval

    (tmp_path / "codex.cmd").write_text(
        '@echo off\r\necho {"type":"turn.completed"}\r\n', encoding="ascii"
    )
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "one", "prompt": "test"}]), encoding="utf-8")
    monkeypatch.setattr(cet6_skill_eval, "CASES_PATH", cases)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert cet6_skill_eval.main(["--run", "--trace-dir", str(tmp_path / "traces")]) == 0
