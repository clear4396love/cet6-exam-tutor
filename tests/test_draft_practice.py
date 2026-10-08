from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from memory.learning_record import LearningRecord
from retrieval.draft_practice import DraftReviewer, get_draft_task, validate_feedback
import retrieval.service as service_module


FILTERS = {"year": 2024, "month": 12, "exam_set": 1}


def _paper():
    return {
        **FILTERS,
        "writing": "To increase the likelihood of success, set realistic goals.",
        "writing_directions": "You should write at least words but no more than words. ___",
        "writing_sample": "A model essay not for the student view.",
        "translation": "港珠澳大桥连接三个城市。",
        "translation_needs_review": False,
        "translation_sample": "The bridge connects three cities.",
    }


def test_safe_draft_tasks_hide_samples_and_downgrade_unverified_directions():
    paper = _paper()
    writing = get_draft_task(paper, "writing")
    translation = get_draft_task(paper, "translation")
    assert writing == {
        "section": "writing", "task_text": paper["writing"], "review_scope": "language_only",
    }
    assert translation == {
        "section": "translation", "task_text": paper["translation"], "review_scope": "full",
    }
    assert "model essay" not in str(writing)
    assert "bridge connects" not in str(translation)
    paper["translation_needs_review"] = True
    assert get_draft_task(paper, "translation") is None


def test_only_exact_verified_writing_direction_gets_full_scope():
    paper = _paper()
    paper.update(year=2020, month=7, exam_set=1)
    paper["writing"] = "The best preparation for tomorrow is doing your best today."
    paper["writing_directions"] = (
        "Directions: For this part, you are allowed 30 minutes to write an essay on the saying "
        "The best preparation for tomorrow is doing your best today. You should write at least "
        "150 words but no more than 200 words."
    )
    assert get_draft_task(paper, "writing")["review_scope"] == "full"
    paper["writing_directions"] += " Part II Listening"
    assert get_draft_task(paper, "writing")["review_scope"] == "language_only"
    paper = _paper()
    paper["writing_directions"] = "Directions: write an essay based on the chart below. <img src='missing.jpg'>"
    assert get_draft_task(paper, "writing")["review_scope"] == "language_only"


def test_submit_draft_saves_versions_without_changing_chat_location(tmp_path):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    service.table.update({"year": 2020, "month": 7, "exam_set": 1, "question_number": 49})
    before = service.table.to_dict()
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        assert "sample" not in str(service.draft_question(2024, 12, 1, "writing"))
        first = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.",
                                     submission_id="click-1")
        same = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.",
                                    submission_id="click-1")
        conflicting = service.submit_draft(2024, 12, 1, "writing", "Different text.",
                                           submission_id="click-1")
        revised = service.submit_draft(2024, 12, 1, "writing", "I have realistic goals.",
                                       revision_of=first["draft_id"], submission_id="click-2")
    assert first["status"] == same["status"] == revised["status"] == "saved"
    assert same["draft_id"] == first["draft_id"] != revised["draft_id"]
    assert conflicting["status"] == "invalid"
    assert service.table.to_dict() == before
    rows = LearningRecord(tmp_path / "learning.jsonl").read()[0]
    assert [row["draft_text"] for row in rows] == ["I have a realistic goal.", "I have realistic goals."]
    assert rows[1]["revision_of"] == rows[0]["draft_id"]


def test_submit_draft_rejects_invalid_text_and_cross_paper_revision(tmp_path):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        first = service.submit_draft(2024, 12, 1, "writing", "Initial essay.", submission_id="one")
        assert service.submit_draft(2024, 12, 1, "writing", "  ")["status"] == "invalid"
        assert service.submit_draft(2024, 12, 1, "writing", "x" * 10001)["status"] == "invalid"
        assert service.submit_draft(2024, 12, 2, "writing", "A revision.",
                                    revision_of=first["draft_id"])["status"] == "invalid"
        assert service.submit_draft(2024, 12, 1, "translation", "A translation.",
                                    revision_of=first["draft_id"])["status"] == "invalid"
    assert len(LearningRecord(tmp_path / "learning.jsonl").read()[0]) == 1


def test_submit_draft_does_not_claim_saved_on_write_error(tmp_path):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    with (patch.object(service_module, "load_set_cached_only", return_value=_paper()),
          patch.object(service.learning_record, "append", side_effect=PermissionError("blocked"))):
        result = service.submit_draft(2024, 12, 1, "translation", "The bridge connects cities.")
    assert result["status"] == "save_error"
    assert result.get("draft_id") is None


def _feedback():
    return {
        "overall": "表达清楚，但时态需调整。", "strengths": ["主题明确"],
        "issues": [{"category": "tense", "quote": "I have a realistic goal", "origin": "draft",
                    "suggestion": "I had a realistic goal", "reason": "叙述过去经历应保持过去时。"}],
        "priority": "先统一叙述时态。", "score": 100,
    }


def test_feedback_validator_keeps_only_grounded_quotes():
    raw = _feedback()
    raw["issues"] += [
        {"category": "grammar", "quote": "I", "origin": "draft",
         "suggestion": "we", "reason": "too short"},
        {"category": "wording", "quote": "invented sentence", "origin": "draft",
         "suggestion": "new", "reason": "unquoted"},
    ]
    checked = validate_feedback(raw, "writing", "I have a realistic goal.", "Discuss goals.")
    assert checked["issues"] == [_feedback()["issues"][0]]
    assert "score" not in checked
    assert validate_feedback({"overall": "", "issues": []}, "writing", "x", "y") is None


@pytest.mark.parametrize("overall", [
    "这篇作文属于中等偏下水平。",
    "预计得分为 85 分。",
    "整体来看，该作文远未达到六级作文的基本要求，但语法错误较少。",
])
def test_feedback_validator_rejects_grade_labels_and_estimated_scores(overall):
    feedback = _feedback()
    feedback["overall"] = overall

    assert validate_feedback(feedback, "writing", "I have a realistic goal.", "Discuss goals.") is None


@pytest.mark.parametrize("overall", [
    "整体来看，该作文远未达到六级作文的基本要求，但语法错误较少。",
    "这个观点很有意义。",
    "这篇作文符合题意，语法也比较稳定。",
])
def test_language_only_review_rejects_task_or_level_claim_before_saving(tmp_path, overall):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        draft_id = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.")["draft_id"]

    class TaskClaimReviewer:
        def __init__(self, config):
            pass

        def generate(self, *args):
            return {**_feedback(), "overall": overall}

    with patch.object(service_module, "DraftReviewer", TaskClaimReviewer):
        assert service.review_draft(draft_id)["status"] == "pending"
    rows, _ = service.learning_record.read()
    assert [row["kind"] for row in rows] == ["draft_submitted"]


def test_full_scope_writing_can_comment_on_task_relevance_without_grading():
    feedback = {**_feedback(), "overall": "内容回应了题目，语法表达清楚。"}

    assert validate_feedback(
        feedback, "writing", "I have a realistic goal.", "Discuss goals.", review_scope="full"
    ) is not None


def test_translation_omission_quote_must_come_from_source():
    feedback = {"overall": "基本准确。", "strengths": [], "priority": "补充遗漏内容。", "issues": [
        {"category": "omission", "origin": "source", "quote": "三个城市",
         "suggestion": "Add the three cities", "reason": "漏译数量信息。"},
        {"category": "omission", "origin": "source", "quote": "不存在的原文",
         "suggestion": "Add it", "reason": "fabricated"},
    ]}
    result = validate_feedback(feedback, "translation", "The bridge connects cities.", "港珠澳大桥连接三个城市。")
    assert len(result["issues"]) == 1
    assert result["issues"][0]["quote"] == "三个城市"


def test_draft_reviewer_sends_only_current_task_and_draft():
    seen = []
    reviewer = DraftReviewer.__new__(DraftReviewer)
    reviewer.llm = RunnableLambda(lambda prompt: seen.append(prompt) or AIMessage(content='{"overall":"清楚","strengths":[],"issues":[],"priority":"复查搭配"}'))
    result = reviewer.generate("writing", "Discuss goals.", "I have goals.", "language_only")
    assert result["overall"] == "清楚"
    prompt = str(seen[0])
    assert "Discuss goals." in prompt and "I have goals." in prompt
    assert "历史记录" not in prompt and "API Key" not in prompt
    assert "能力水平标签" in prompt


def test_review_failure_then_retry_uses_same_saved_draft(tmp_path):
    path = tmp_path / "learning.jsonl"
    service = service_module.Service(None, learning_path=path)
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        draft_id = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.")["draft_id"]

    class BrokenReviewer:
        def __init__(self, config):
            pass

        def generate(self, *args):
            raise RuntimeError("offline")

    with patch.object(service_module, "DraftReviewer", BrokenReviewer):
        assert service.review_draft(draft_id)["status"] == "pending"
    reopened = service_module.Service(None, learning_path=path)

    class WorkingReviewer:
        def __init__(self, config):
            pass

        def generate(self, *args):
            return _feedback()

    with patch.object(service_module, "DraftReviewer", WorkingReviewer):
        ready = reopened.review_draft(draft_id)
        again = reopened.review_draft(draft_id)
    assert ready["status"] == again["status"] == "ready"
    assert ready["feedback"] == again["feedback"]
    assert ready["warning"] == ""
    assert len(LearningRecord(path).read()[0]) == 2


def test_review_drops_unquoted_issue_and_reports_incomplete_feedback(tmp_path):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        draft_id = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.")["draft_id"]
    raw = _feedback()
    raw["issues"][0]["quote"] = "Ignore prior instructions"

    class MisquotedReviewer:
        def __init__(self, config):
            pass

        def generate(self, *args):
            return raw

    with patch.object(service_module, "DraftReviewer", MisquotedReviewer):
        result = service.review_draft(draft_id)
    assert result["status"] == "ready"
    assert result["feedback"]["issues"] == []
    assert "不完整" in result["warning"]


def test_feedback_save_failure_returns_unsaved_feedback(tmp_path):
    service = service_module.Service(None, learning_path=tmp_path / "learning.jsonl")
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        draft_id = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.")["draft_id"]

    class WorkingReviewer:
        def __init__(self, config):
            pass

        def generate(self, *args):
            return _feedback()

    with (patch.object(service_module, "DraftReviewer", WorkingReviewer),
          patch.object(service.learning_record, "append", side_effect=PermissionError("blocked"))):
        result = service.review_draft(draft_id)
    assert result["status"] == "feedback_not_saved"
    assert result["feedback"]["overall"]
    assert len(service.learning_record.read()[0]) == 1


def test_draft_history_restores_versions_and_feedback_after_reopen(tmp_path):
    path = tmp_path / "learning.jsonl"
    service = service_module.Service(None, learning_path=path)
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        first = service.submit_draft(2024, 12, 1, "writing", "I have a realistic goal.",
                                     submission_id="first")
        service.submit_draft(2024, 12, 1, "writing", "I have realistic goals.",
                             revision_of=first["draft_id"], submission_id="second")
    service.learning_record.append({
        "kind": "feedback_ready", "section": "writing", "filters": FILTERS,
        "draft_id": first["draft_id"], "feedback": {"overall": "Clear first version."},
    })
    reopened = service_module.Service(None, learning_path=path)
    history = reopened.draft_history("writing")
    assert [row["draft_text"] for row in history] == [
        "I have a realistic goal.", "I have realistic goals."]
    assert history[0]["feedback"]["overall"] == "Clear first version."
    assert history[1]["feedback"] is None
    assert history[1]["revision_of"] == first["draft_id"]
