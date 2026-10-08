"""Writable Skill eval checks the isolated archive, not just the final prose."""

import json
import shutil
from pathlib import Path

import pytest

from memory.learning_record import LearningRecord
from tools.cet6_skill_multiturn_eval import (build_command, reviewed_history, retry_progress,
                                             retry_review, run_flow, run_turn, score_drafts,
                                             thread_id_from_events)


def _draft(text: str, revision_of: str | None = None, section: str = "translation") -> dict:
    return {
        "kind": "draft_submitted", "section": section,
        "filters": {"year": 2024, "month": 12, "exam_set": 1},
        "draft_text": text,
        "task_text": "请翻译北斗。" if section == "translation" else "To increase the likelihood of success...",
        "review_scope": "full" if section == "translation" else "language_only",
        "revision_of": revision_of, "submission_id": f"eval-{text}",
    }


def test_build_command_preserves_archive_and_workspace_write_on_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\tools\codex.cmd")
    archive = tmp_path / "learning_events.jsonl"
    first = build_command("submit prompt", archive)
    resumed = build_command("revise prompt", archive, thread_id="thread-123")

    setting = "shell_environment_policy.set.EXAM_TUTOR_LEARNING_PATH=" + json.dumps(
        archive.as_posix())
    assert first[:4] == [r"C:\tools\codex.cmd", "exec", "--json", "--sandbox"]
    assert "workspace-write" in first and "--ephemeral" not in first
    assert setting in first and setting in resumed
    assert resumed[:4] == [r"C:\tools\codex.cmd", "exec", "resume", "--json"]
    assert "thread-123" in resumed and "--ephemeral" not in resumed
    assert 'sandbox_mode="workspace-write"' in resumed


def test_thread_id_requires_a_real_started_event():
    assert thread_id_from_events([{"type": "thread.started", "thread_id": "thread-123"}]) == "thread-123"
    assert thread_id_from_events([{"type": "turn.completed"}]) is None


def test_run_turn_passes_isolated_archive_and_retains_trace(tmp_path, monkeypatch):
    from tools import cet6_skill_multiturn_eval as evaluator

    archive = tmp_path / "learning_events.jsonl"
    trace = tmp_path / "submit.jsonl"

    def capture(command, path, env, timeout):
        assert "tools.cet6_skill" not in " ".join(command)  # Agent, not harness, chooses tool.
        assert env["EXAM_TUTOR_LEARNING_PATH"] == str(archive)
        assert env["LANGSMITH_TRACING"] == "false"
        assert timeout > 0
        path.write_text('{"type":"thread.started","thread_id":"thread-123"}\n'
                        '{"type":"turn.completed"}\n', encoding="utf-8")
        return 0

    monkeypatch.setattr(evaluator, "capture_trace", capture)
    result = run_turn("submit prompt", archive, trace)
    assert result["exit_code"] == 0
    assert result["thread_id"] == "thread-123"
    assert result["completed"] is True
    assert trace.exists()


def test_build_command_enables_network_only_when_explicitly_requested(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    assert "sandbox_workspace_write.network_access=true" not in build_command("submit", archive)
    assert "sandbox_workspace_write.network_access=true" in build_command(
        "review", archive, network_access=True)


def test_score_drafts_requires_exact_text_and_one_linked_revision(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft("The Beidou system are useful for many countries."))
    record.append(_draft("The Beidou system is useful for many countries.", first["draft_id"]))

    assert score_drafts(archive,
                        "The Beidou system are useful for many countries.",
                        "The Beidou system is useful for many countries.") == []


def test_score_drafts_rejects_wrong_parent_and_extra_submission(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    record.append(_draft("first"))
    record.append(_draft("revised", "unrelated-draft"))
    record.append(_draft("unexpected"))

    failed = score_drafts(archive, "first", "revised")
    assert "draft_count" in failed
    assert "revision_parent" in failed


def test_score_drafts_does_not_treat_feedback_as_an_extra_draft(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft("first"))
    record.append({"kind": "feedback_ready", "section": "translation",
                   "filters": first["filters"], "draft_id": first["draft_id"],
                   "feedback": {"overall": "继续练习"}})
    record.append(_draft("revised", first["draft_id"]))

    assert score_drafts(archive, "first", "revised") == []


def test_score_drafts_checks_writing_scope_and_linked_revision(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    first_text = "People should set realistic goal because it help them succeed."
    revised_text = "People should set realistic goals because this helps them succeed."
    first = record.append(_draft(first_text, section="writing"))
    record.append(_draft(revised_text, first["draft_id"], section="writing"))

    assert score_drafts(archive, first_text, revised_text, section="writing") == []


def test_score_drafts_rejects_writing_scope_that_would_allow_task_scoring(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    first_text = "People should set realistic goal because it help them succeed."
    revised_text = "People should set realistic goals because this helps them succeed."
    first = record.append(_draft(first_text, section="writing"))
    revised = _draft(revised_text, first["draft_id"], section="writing")
    revised["review_scope"] = "full"
    record.append(revised)

    assert "review_scope" in score_drafts(archive, first_text, revised_text, section="writing")


def test_run_flow_writing_uses_writing_commands_and_scope_without_translation_claims(
        monkeypatch, tmp_path):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    prompts = []
    archive = tmp_path / "writing-run" / "learning_events.jsonl"
    first_text = evaluator.WRITING_FIRST_DRAFT
    revised_text = evaluator.WRITING_REVISED_DRAFT

    def saved_turn(prompt, used_archive, trace, thread_id=None, **_kwargs):
        prompts.append(prompt)
        record = LearningRecord(used_archive)
        current = [event for event in record.read()[0] if event["kind"] == "draft_submitted"]
        if "原稿历史" in prompt:
            message = "\n".join(row["draft_text"] + " " + row["draft_id"] for row in current)
            message += " 已保存评语指出主谓一致和时态问题。"
            command = "python -m tools.cet6_skill history --section writing"
        elif "学习进度" in prompt:
            message = "作文提交两版。"
            command = "python -m tools.cet6_skill progress"
        elif "修改稿如下" in prompt:
            parent = next(row for row in current if row["draft_text"] == first_text)
            saved = record.append(_draft(revised_text, parent["draft_id"], section="writing"))
            message = f"已保存作文修改稿，编号 {saved['draft_id']}。语言评语：时态和语法。"
            command = "python -m tools.cet6_skill submit 2024 12 1 writing --revision-of " + parent["draft_id"]
        elif "原稿如下" in prompt:
            saved = record.append(_draft(first_text, section="writing"))
            message = f"已保存作文原稿，编号 {saved['draft_id']}。语言评语：主谓一致和时态。"
            command = "python -m tools.cet6_skill submit 2024 12 1 writing"
        events = [{"type": "thread.started", "thread_id": thread_id or "thread-writing"},
                  {"type": "item.completed", "item": {"type": "command_execution",
                   "command": command,
                   "exit_code": 0}},
                  {"type": "item.completed", "item": {"type": "agent_message",
                   "text": message}},
                  {"type": "turn.completed"}]
        trace.write_text("", encoding="utf-8")
        return {"exit_code": 0, "thread_id": thread_id or "thread-writing",
                "completed": True, "events": events}

    monkeypatch.setattr(evaluator, "run_turn", saved_turn)
    result = evaluator.run_flow(tmp_path / "writing-run", section="writing")

    assert result["status"] == "passed", result
    assert "writing" in " ".join(prompts[0:1]).lower() or "作文" in prompts[0]
    assert "评价任务合规" in prompts[0]
    assert "翻译" not in prompts[0]


def test_run_flow_rejects_directory_outside_isolated_eval_root(tmp_path):
    with pytest.raises(ValueError, match="isolated"):
        run_flow(tmp_path)


def test_run_flow_stops_before_revision_if_submit_was_not_saved(monkeypatch, tmp_path):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    calls = []

    def completed_without_archive(prompt, archive, trace, **kwargs):
        calls.append(prompt)
        return {"exit_code": 0, "thread_id": "thread-123", "completed": True,
                "events": [{"type": "turn.completed"}]}

    monkeypatch.setattr(evaluator, "run_turn", completed_without_archive)
    result = run_flow(tmp_path / "one-run")
    assert result["status"] == "stopped"
    assert result["reason"] == "first_draft_not_saved"
    assert len(calls) == 1


def test_retry_progress_uses_existing_drafts_without_resubmitting(monkeypatch, tmp_path):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    run_dir = tmp_path / "one-run"
    run_dir.mkdir()
    archive = run_dir / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft("The Beidou system are useful for many countries."))
    record.append(_draft("The Beidou system is useful for many countries.", first["draft_id"]))
    before = archive.read_bytes()
    calls = []

    def completed_progress(prompt, used_archive, trace, **kwargs):
        calls.append((prompt, used_archive, trace))
        return {"exit_code": 0, "thread_id": "new-thread", "completed": True,
                "events": [
                    {"type": "item.completed", "item": {"type": "command_execution",
                     "command": "python -m tools.cet6_skill progress", "exit_code": 0}},
                    {"type": "item.completed", "item": {"type": "agent_message",
                     "text": "翻译已提交两版，请继续修改。"}},
                    {"type": "turn.completed"},
                ]}

    monkeypatch.setattr(evaluator, "run_turn", completed_progress)
    report = retry_progress(run_dir)
    assert report["status"] == "passed"
    assert len(calls) == 1 and calls[0][1] == archive
    assert calls[0][2].parent == run_dir and "progress-retry" in calls[0][2].name
    assert archive.read_bytes() == before


def test_retry_review_only_adds_feedback_for_saved_draft(monkeypatch, tmp_path):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    run_dir = tmp_path / "one-run"
    run_dir.mkdir()
    archive = run_dir / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft("The Beidou system are useful for many countries."))
    revised = record.append(_draft("The Beidou system is useful for many countries.", first["draft_id"]))
    calls = []

    def completed_review(prompt, used_archive, trace, **kwargs):
        calls.append((prompt, kwargs))
        LearningRecord(used_archive).append({
            "kind": "feedback_ready", "section": "translation", "filters": first["filters"],
            "draft_id": first["draft_id"], "feedback": {"overall": "主谓一致已改正"},
        })
        return {"exit_code": 0, "thread_id": "new-thread", "completed": True,
                "events": [
                    {"type": "item.completed", "item": {"type": "command_execution",
                     "command": f"python -m tools.cet6_skill review {first['draft_id']}", "exit_code": 0}},
                    {"type": "item.completed", "item": {"type": "agent_message",
                     "text": "已重新评阅：主谓一致已改正。"}},
                    {"type": "turn.completed"},
                ]}

    monkeypatch.setattr(evaluator, "run_turn", completed_review)
    result = retry_review(run_dir, first["draft_id"])
    assert result["status"] == "passed"
    assert calls[0][1]["network_access"] is True
    rows, _ = LearningRecord(archive).read()
    assert [row["kind"] for row in rows] == ["draft_submitted", "draft_submitted", "feedback_ready"]
    assert rows[-1]["draft_id"] == first["draft_id"]


@pytest.mark.parametrize(
    ("stored_feedback", "reply_feedback", "expected_status"),
    [("评语指出语法、时态和用词问题。", "评语指出语法、时态和用词问题。", "passed"),
     ("修正过去经历中的动词形式和主谓一致，注意 confident/confidence 的词性。",
      "过去经历中的动词形式和主谓一致需要修正；confident/confidence 的词性不同。",
      "passed"),
     ("评语指出语法问题，预计可得 85 分。", "评语指出语法问题，预计可得 85 分。", "failed"),
     ("作文整体属于中等偏下水平。", "评语指出主谓一致和时态问题。", "failed"),
     ("该作文远未达到六级作文的基本要求，语法问题较少。",
      "评语指出主谓一致和时态问题。", "failed")],
)
def test_reviewed_history_enforces_writing_language_only_scope(
        monkeypatch, tmp_path, stored_feedback, reply_feedback, expected_status):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    run_dir = tmp_path / "one-run"
    run_dir.mkdir()
    archive = run_dir / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft(evaluator.WRITING_FIRST_DRAFT, section="writing"))
    revised = record.append(_draft(evaluator.WRITING_REVISED_DRAFT, first["draft_id"],
                                   section="writing"))
    for draft in (first, revised):
        record.append({"kind": "feedback_ready", "section": "writing",
                       "filters": draft["filters"], "draft_id": draft["draft_id"],
                       "feedback": {"overall": stored_feedback, "strengths": [], "issues": [],
                                    "priority": "check tense"}})
    message = (evaluator.WRITING_FIRST_DRAFT + " " + first["draft_id"] + "\n"
               + evaluator.WRITING_REVISED_DRAFT + " " + revised["draft_id"] + "\n"
               + reply_feedback)

    def history_turn(prompt, used_archive, trace, **_kwargs):
        assert used_archive == archive
        assert "只检查语言" in prompt
        return {"exit_code": 0, "thread_id": "new-writing-chat", "completed": True,
                "events": [
                    {"type": "item.completed", "item": {"type": "command_execution",
                     "command": "python -m tools.cet6_skill history --section writing",
                     "exit_code": 0}},
                    {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
                    {"type": "turn.completed"},
                ]}

    monkeypatch.setattr(evaluator, "run_turn", history_turn)
    result = evaluator.reviewed_history(run_dir, section="writing")

    assert result["status"] == expected_status
    if expected_status == "failed":
        assert "writing_scope_violation" in result["failed"]


def test_reviewed_history_stops_before_agent_if_feedback_is_missing(monkeypatch, tmp_path):
    from tools import cet6_skill_multiturn_eval as evaluator

    monkeypatch.setattr(evaluator, "RUN_ROOT", tmp_path)
    run_dir = tmp_path / "one-run"
    run_dir.mkdir()
    archive = run_dir / "learning_events.jsonl"
    record = LearningRecord(archive)
    first = record.append(_draft("The Beidou system are useful for many countries."))
    record.append(_draft("The Beidou system is useful for many countries.", first["draft_id"]))
    monkeypatch.setattr(evaluator, "run_turn", lambda *_args, **_kwargs: pytest.fail("must not call agent"))

    result = reviewed_history(run_dir)
    assert result["status"] == "stopped"
    assert result["reason"] == "feedback_not_saved"
