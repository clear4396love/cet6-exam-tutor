import json
from pathlib import Path
from unittest.mock import patch

import pytest

from memory.learning_record import LearningRecord


FILTERS = {"year": 2024, "month": 12, "exam_set": 1}


def reading_event(correct=True):
    return {
        "kind": "reading_attempt", "section": "reading",
        "filters": {**FILTERS, "question_number": 36},
        "stage": "attempt_correct" if correct else "attempt_wrong",
        "attempt_answer": "C" if correct else "A", "attempt_correct": correct,
    }


def draft_event(submission_id="click-1"):
    return {
        "kind": "draft_submitted", "section": "writing", "filters": FILTERS,
        "draft_text": "A short student essay.", "task_text": "Discuss realistic goals.",
        "review_scope": "language_only", "revision_of": None,
        "submission_id": submission_id,
    }


def test_persists_three_kinds_and_keeps_append_order(tmp_path):
    path = tmp_path / "events.jsonl"
    record = LearningRecord(path)
    assert not path.exists()
    first = record.append(reading_event(False))
    draft = record.append(draft_event())
    feedback = record.append({
        "kind": "feedback_ready", "section": "writing", "filters": FILTERS,
        "draft_id": draft["draft_id"], "feedback": {"overall": "Clear but brief."},
    })
    rows, warnings = LearningRecord(path).read()
    assert warnings == []
    assert [row["event_id"] for row in rows] == [first["event_id"], draft["event_id"], feedback["event_id"]]
    assert draft["draft_id"] == draft["event_id"]
    assert all(row["ts"].endswith("+00:00") or "+" in row["ts"] for row in rows)
    assert "answer" not in rows[0] and "answer_keys" not in rows[0]


def test_same_submission_and_feedback_are_idempotent_across_instances(tmp_path):
    path = tmp_path / "events.jsonl"
    first = LearningRecord(path).append(draft_event())
    again = LearningRecord(path).append(draft_event())
    assert again == first
    event = {"kind": "feedback_ready", "section": "writing", "filters": FILTERS,
             "draft_id": first["draft_id"], "feedback": {"overall": "Useful."}}
    first_feedback = LearningRecord(path).append(event)
    assert LearningRecord(path).append(event) == first_feedback
    assert len(LearningRecord(path).read()[0]) == 2


def test_bad_lines_are_skipped_without_losing_valid_ones(tmp_path):
    path = tmp_path / "events.jsonl"
    record = LearningRecord(path)
    record.append(reading_event())
    with path.open("ab") as handle:
        handle.write(b"{not json}\n\xff\n")
        handle.write(b'{"kind":"reading_attempt","attempt_correct":"false"}\n')
        handle.write(b'{"kind":[]}\n')
    rows, warnings = record.read()
    assert len(rows) == 1
    assert len(warnings) == 4
    assert record.append(reading_event(False))["attempt_correct"] is False
    assert len(record.read()[0]) == 2


def test_unhashable_values_in_saved_fields_are_skipped(tmp_path):
    path = tmp_path / "events.jsonl"
    record = LearningRecord(path)
    valid = record.append(draft_event())
    with path.open("a", encoding="utf-8") as handle:
        for field in ("section", "review_scope"):
            handle.write(json.dumps({**valid, field: []}) + "\n")
    rows, warnings = record.read()
    assert rows == [valid]
    assert len(warnings) == 2


def test_rejects_unknown_fields_and_wrong_types(tmp_path):
    record = LearningRecord(tmp_path / "events.jsonl")
    for key in ("answer", "api_key"):
        with pytest.raises(ValueError):
            record.append({**reading_event(), key: "secret"})
    with pytest.raises(ValueError):
        record.append({**reading_event(), "attempt_correct": "true"})
    assert not record.path.exists()


def test_path_override_and_write_errors_are_visible(tmp_path, monkeypatch):
    env_path = tmp_path / "from-env.jsonl"
    monkeypatch.setenv("EXAM_TUTOR_LEARNING_PATH", str(env_path))
    assert LearningRecord().path == env_path
    explicit = tmp_path / "explicit.jsonl"
    assert LearningRecord(explicit).path == explicit
    assert explicit != Path.home() / ".exam-tutor" / "learning_events.jsonl"
    with patch("pathlib.Path.open", side_effect=PermissionError("read only")):
        with pytest.raises(PermissionError):
            LearningRecord(explicit).append(reading_event())


def test_read_permission_error_is_not_silent(tmp_path):
    record = LearningRecord(tmp_path / "events.jsonl")
    record.append(reading_event())
    with patch("pathlib.Path.open", side_effect=PermissionError("blocked")):
        rows, warnings = record.read()
    assert rows == []
    assert warnings and "blocked" in warnings[0]
