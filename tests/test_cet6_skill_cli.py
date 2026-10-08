"""The Codex Skill adapter must not invent progress or expose draft text."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from memory.learning_record import LearningRecord


ROOT = Path(__file__).resolve().parents[1]


def _draft(section: str, text: str) -> dict:
    return {
        "kind": "draft_submitted", "section": section,
        "filters": {"year": 2024, "month": 12, "exam_set": 1},
        "draft_text": text, "task_text": "Write about the topic.",
        "review_scope": "language_only", "revision_of": None,
        "submission_id": f"skill-test-{section}",
    }


def test_progress_reads_local_writing_translation_without_exposing_drafts(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    record.append(_draft("writing", "PRIVATE-WRITING-TEXT"))
    record.append(_draft("translation", "PRIVATE-TRANSLATION-TEXT"))
    before = archive.read_bytes()

    env = {**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(archive)}
    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "progress"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    progress = json.loads(result.stdout)
    assert progress["writing_count"] == 1
    assert progress["translation_count"] == 1
    assert "重试评阅" in progress["next_writing_step"]
    assert "重试评阅" in progress["next_translation_step"]
    assert "PRIVATE-" not in result.stdout
    assert "reading" not in progress
    assert archive.read_bytes() == before


def test_progress_reports_missing_archive_instead_of_claiming_zero_history(tmp_path):
    missing = tmp_path / "not-created.jsonl"
    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "progress"],
        cwd=ROOT,
        env={**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(missing)},
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    progress = json.loads(result.stdout)
    assert progress["status"] == "no_archive"
    assert "writing_count" not in progress
    assert "translation_count" not in progress
    assert not missing.exists()


def test_progress_does_not_echo_feedback_that_quotes_a_private_draft(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    record = LearningRecord(archive)
    saved = record.append(_draft("writing", "PRIVATE-WRITING-TEXT"))
    record.append({
        "kind": "feedback_ready", "section": "writing",
        "filters": saved["filters"], "draft_id": saved["draft_id"],
        "feedback": {"priority": "Rewrite PRIVATE-WRITING-TEXT"},
    })

    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "progress"],
        cwd=ROOT,
        env={**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(archive)},
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    progress = json.loads(result.stdout)
    assert progress["writing_count"] == 1
    assert "评语" in progress["next_writing_step"]
    assert "修改原稿" in progress["next_writing_step"]
    assert "Streamlit" not in progress["next_writing_step"]
    assert "PRIVATE-WRITING-TEXT" not in result.stdout


def test_cached_only_service_never_calls_pdf_parser_on_cache_miss(monkeypatch, tmp_path):
    from memory.episode import Episode
    import retrieval.service as service_module

    class OfflineIntent:
        def __init__(self, *_):
            pass

        def merged(self, *_):
            return "NEW_QUESTION", None, False

    def unsafe_parser(*_):
        raise AssertionError("PDF parsing must not run for Skill requests")

    monkeypatch.setattr(service_module, "Find_Intent", OfflineIntent)
    monkeypatch.setattr(service_module, "load_set", unsafe_parser)
    monkeypatch.setattr(service_module, "load_set_cached_only", lambda *_: None)

    app = service_module.Service(None, cached_only=True)
    app.episode = Episode("skill-cache-miss", out_dir=str(tmp_path))
    answer = app.process("2024年12月第1套第43题")

    assert answer.startswith("【未定位到原题】")
    assert app._tr["stage"] == "cache_miss_paper"


def test_cached_only_service_uses_cached_key_when_paper_exists(monkeypatch, tmp_path):
    from memory.episode import Episode
    import retrieval.service as service_module
    from tests.test_state_and_trace import FAKE_PAPER, FakeFindIntent

    monkeypatch.setattr(service_module, "Find_Intent", FakeFindIntent)
    monkeypatch.setattr(service_module, "load_set_cached_only", lambda *_: FAKE_PAPER)
    monkeypatch.setattr(service_module, "load_set", lambda *_: None)

    app = service_module.Service(None, cached_only=True)
    app.episode = Episode("skill-cache-hit", out_dir=str(tmp_path))
    answer = app.process("2024年12月第1套第43题")

    assert answer.startswith("第43题答案:A")
    assert app._tr["answer_keys"] == "A"


def test_ask_with_cached_paper_uses_existing_service(monkeypatch, capsys):
    from tools import cet6_skill

    class CachedOnlyService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def process(self, question):
            assert question == "2024年12月第1套第43题"
            return "第43题选 I"

    monkeypatch.setattr(cet6_skill, "Service", CachedOnlyService)

    assert cet6_skill.main(["ask", "2024年12月第1套第43题"]) == 0
    assert capsys.readouterr().out.strip() == "第43题选 I"


@pytest.mark.parametrize("question", [
    "2024年12月第1套翻译怎么写",
    "2024年12月第1套第43题翻译怎么写",
])
def test_ask_rejects_translation_routes_before_loading_service(monkeypatch, capsys, question):
    from tools import cet6_skill

    def forbidden_service(*_args, **_kwargs):
        raise AssertionError("translation route must not reach Service.process")

    monkeypatch.setattr(cet6_skill, "Service", forbidden_service)
    assert cet6_skill.main(["ask", question]) == 2
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "unsupported"
    assert "sample" not in response and "analysis" not in response


def test_progress_marks_corrupted_archive_partial(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    LearningRecord(archive).append(_draft("translation", "PRIVATE-TRANSLATION-TEXT"))
    with archive.open("ab") as handle:
        handle.write(b"{broken}\n")

    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "progress"],
        cwd=ROOT,
        env={**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(archive)},
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    progress = json.loads(result.stdout)
    assert progress["status"] == "partial"
    assert progress["translation_count"] == 1
    assert progress["history_warnings"]
    assert "PRIVATE-" not in result.stdout


def test_task_returns_only_cached_practice_prompt(monkeypatch, capsys):
    from tools import cet6_skill

    class CachedService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def draft_question(self, year, month, exam_set, section):
            assert (year, month, exam_set, section) == (2024, 12, 1, "translation")
            return {"section": "translation", "task_text": "请翻译这段中文。", "review_scope": "full"}

    monkeypatch.setattr(cet6_skill, "Service", CachedService)
    assert cet6_skill.main(["task", "2024", "12", "1", "translation"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown == {"status": "ready", "section": "translation",
                     "task_text": "请翻译这段中文。", "review_scope": "full"}
    assert "sample" not in shown and "analysis" not in shown


def test_submit_reads_utf8_file_saves_then_reviews_revision(monkeypatch, capsys, tmp_path):
    from tools import cet6_skill

    draft_file = tmp_path / "student.txt"
    draft_file.write_text("Beidou provides navigation. 北斗", encoding="utf-8")
    calls = []

    class CachedService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def submit_draft(self, year, month, exam_set, section, text, revision_of=None, submission_id=None):
            calls.append(("save", year, month, exam_set, section, text, revision_of))
            return {"status": "saved", "draft_id": "version-2"}

        def review_draft(self, draft_id):
            calls.append(("review", draft_id))
            return {"status": "ready", "feedback": {"overall": "语法正确", "issues": []}, "warning": ""}

    monkeypatch.setattr(cet6_skill, "Service", CachedService)
    assert cet6_skill.main(["submit", "2024", "12", "1", "translation",
                            "--text-file", str(draft_file), "--revision-of", "version-1"]) == 0
    assert calls == [("save", 2024, 12, 1, "translation", "Beidou provides navigation. 北斗", "version-1"),
                     ("review", "version-2")]
    assert json.loads(capsys.readouterr().out) == {
        "status": "ready", "draft_id": "version-2",
        "feedback": {"overall": "语法正确", "issues": []}, "warning": ""}
    assert draft_file.exists()  # The CLI must not delete a user-supplied file.


def test_submit_keeps_saved_draft_when_review_is_pending(monkeypatch, capsys, tmp_path):
    from tools import cet6_skill

    draft_file = tmp_path / "essay.txt"
    draft_file.write_text("My goal is realistic.", encoding="utf-8")

    class CachedService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def submit_draft(self, *_args, **_kwargs):
            return {"status": "saved", "draft_id": "saved-before-review"}

        def review_draft(self, _draft_id):
            return {"status": "pending"}

    monkeypatch.setattr(cet6_skill, "Service", CachedService)
    assert cet6_skill.main(["submit", "2024", "12", "1", "writing",
                            "--text-file", str(draft_file)]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "pending", "draft_id": "saved-before-review"}


def test_review_and_history_are_explicit_read_paths(monkeypatch, capsys, tmp_path):
    from tools import cet6_skill

    archive = tmp_path / "learning_events.jsonl"
    LearningRecord(archive).append(_draft("writing", "Private student essay"))
    monkeypatch.setenv("EXAM_TUTOR_LEARNING_PATH", str(archive))

    class CachedService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def review_draft(self, draft_id):
            assert draft_id == "saved-draft"
            return {"status": "ready", "feedback": {"priority": "检查时态"}, "warning": ""}

        def draft_history(self, section=None):
            assert section == "writing"
            return [{"draft_id": "saved-draft", "draft_text": "Private student essay",
                     "revision_of": None, "feedback": {"priority": "检查时态"}}]

    monkeypatch.setattr(cet6_skill, "Service", CachedService)
    assert cet6_skill.main(["review", "saved-draft"]) == 0
    assert json.loads(capsys.readouterr().out)["feedback"]["priority"] == "检查时态"
    assert cet6_skill.main(["history", "--section", "writing"]) == 0
    assert json.loads(capsys.readouterr().out)["drafts"][0]["draft_text"] == "Private student essay"


def test_history_distinguishes_missing_archive_from_empty_history(tmp_path):
    missing = tmp_path / "missing.jsonl"
    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "history"], cwd=ROOT,
        env={**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(missing)},
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "no_archive", "drafts": [], "history_warnings": []}
    assert not missing.exists()


def test_history_reports_partial_archive_without_hiding_valid_drafts(tmp_path):
    archive = tmp_path / "learning_events.jsonl"
    saved = LearningRecord(archive).append(_draft("writing", "Recoverable essay"))
    with archive.open("ab") as handle:
        handle.write(b"{broken}\n")
    result = subprocess.run(
        [sys.executable, "-m", "tools.cet6_skill", "history", "--section", "writing"], cwd=ROOT,
        env={**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(archive)},
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    history = json.loads(result.stdout)
    assert history["status"] == "partial"
    assert history["drafts"][0]["draft_id"] == saved["draft_id"]
    assert history["history_warnings"]


def test_reference_requires_explicit_confirmation(monkeypatch, capsys):
    from tools import cet6_skill

    calls = []

    class CachedService:
        def __init__(self, _config, *, cached_only=False):
            assert cached_only is True

        def draft_question(self, year, month, exam_set, section):
            calls.append("task")
            return {"task_text": "Write about trust.", "section": "writing", "review_scope": "language_only"}

        def reference_material(self, year, month, exam_set, section, expected_task_text):
            calls.append("reference")
            assert expected_task_text == "Write about trust."
            return {"status": "ready", "sample": "SAMPLE", "analysis": "ANALYSIS"}

    monkeypatch.setattr(cet6_skill, "Service", CachedService)
    with pytest.raises(SystemExit) as exc:
        cet6_skill.main(["reference", "2024", "12", "1", "writing"])
    assert exc.value.code == 2 and calls == []
    capsys.readouterr()
    assert cet6_skill.main(["reference", "2024", "12", "1", "writing", "--confirm"]) == 0
    assert calls == ["task", "reference"]
    assert json.loads(capsys.readouterr().out)["sample"] == "SAMPLE"
