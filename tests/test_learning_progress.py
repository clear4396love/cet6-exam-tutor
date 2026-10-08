from unittest.mock import patch

from memory.learning_record import LearningRecord
from retrieval.practice import summarize_learning
import retrieval.service as service_module


def attempt(year, month, exam_set, question_number, correct):
    return {
        "kind": "reading_attempt", "section": "reading",
        "filters": {"year": year, "month": month, "exam_set": exam_set,
                    "question_number": question_number},
        "stage": "attempt_correct" if correct else "attempt_wrong",
        "attempt_answer": "C" if correct else "A", "attempt_correct": correct,
    }


def draft(section="writing", draft_id="draft-1", revision_of=None):
    return {"kind": "draft_submitted", "section": section, "draft_id": draft_id,
            "revision_of": revision_of,
            "filters": {"year": 2024, "month": 12, "exam_set": 1}}


def feedback(draft_id="draft-1"):
    return {"kind": "feedback_ready", "section": "writing", "draft_id": draft_id,
            "feedback": {"overall": "尚可", "strengths": [], "issues": [], "priority": "统一时态"}}


def test_full_coordinates_and_latest_attempt_control_recommendation():
    events = [attempt(2024, 12, 1, 36, False), attempt(2025, 6, 1, 36, False),
              attempt(2024, 12, 1, 36, False)]
    summary = summarize_learning(events)
    assert summary["reading"]["repeated_misses"] == [36]
    assert len(summary["repetition_groups"]) == 2
    first = next(group for group in summary["repetition_groups"] if group["year"] == 2024)
    assert first == {"year": 2024, "month": 12, "exam_set": 1,
                     "question_number": 36, "wrong_count": 2, "latest_correct": False}
    assert "2024年12月第1套第36题" in summary["next_action"]
    corrected = summarize_learning(events + [attempt(2024, 12, 1, 36, True)])
    assert "2024年12月第1套第36题" not in corrected["next_action"]
    assert corrected["repetition_groups"][0]["latest_correct"] is True
    assert corrected["reading"]["attempt_count"] == 4


def test_latest_uses_append_order_not_timestamp_and_respects_preference():
    events = [attempt(2024, 12, 1, 36, False), draft(), feedback()]
    summary = summarize_learning(events)
    assert summary["writing_count"] == 1 and summary["translation_count"] == 0
    assert summary["latest_feedback_status"] == "ready"
    assert "AI 参考评语" in summary["next_action"] and "统一时态" in summary["next_action"]
    reading = summarize_learning(events, preferred_section="reading")
    assert "2024年12月第1套第36题" in reading["next_action"]
    assert reading["next_action_target"]["question_number"] == 36


def test_pending_draft_recommends_retry_and_revisions_count_separately():
    events = [draft(), draft("writing", "draft-2", "draft-1")]
    summary = summarize_learning(events)
    assert summary["writing_count"] == 2 and summary["writing_revisions"] == 1
    assert summary["reading"]["attempt_count"] == 0
    assert summary["latest_feedback_status"] == "pending"
    assert "重试评阅" in summary["next_action"]
    assert summary["next_action_target"]["draft_id"] == "draft-2"


def test_no_record_proposes_only_one_collected_practice():
    result = summarize_learning([])
    assert result["reading"]["tier"] == "plan_insufficient_data"
    assert result["next_action"] == "选择一道已收录的阅读题，先提交一次答案。"
    assert result["next_action_target"] is None


def test_service_progress_exposes_warnings_and_downgrades_missing_cache(tmp_path):
    path = tmp_path / "learning.jsonl"
    LearningRecord(path).append(attempt(2024, 12, 1, 36, False))
    with path.open("ab") as handle:
        handle.write(b"{broken}\n")
    service = service_module.Service(None, learning_path=path)
    with patch.object(service_module, "load_set_cached_only", return_value=None):
        progress = service.learning_progress()
    assert progress["reading"]["attempt_count"] == 1
    assert progress["history_warnings"]
    assert progress["next_action"] == "选择另一套已收录的阅读题，先提交一次答案。"
