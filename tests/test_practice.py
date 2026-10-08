"""The practice path must not expose KEYS before submission."""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from memory.episode import Episode
from retrieval.generation import AnswerGeneration
from retrieval.practice import get_practice_item, grade_attempt, summarize_attempts
import retrieval.service as service_module


def _paper():
    return {
        "questions": {"36": {"stem": "  A clue  ", "answer": "C"}},
        "paragraphs": {"A": "First paragraph", "C": "Correct paragraph"},
    }


def _cloze_paper():
    words = {letter: f"word{letter.lower()}" for letter in "ABCDEFGHIJKLMNO"}
    return {"section_a": {
        "practice_text": " ".join(f"context {{{{{n}}}}}" for n in range(26, 36)),
        "text": " ".join("context" for _ in range(10)),
        "words": words,
        "questions": {str(n): {"answer": "ABCDEFGHIJ"[n - 26],
                                "answer_word": words["ABCDEFGHIJ"[n - 26]]}
                      for n in range(26, 36)},
    }}


def _section_c_paper():
    return {"section_c": {"passages": [
        {"text": "First passage explains why sleep helps memory.",
         "questions": {"46": {"stem": "Why is sleep useful?", "answer": "B",
                              "options": {"A": "It saves money", "B": "It helps memory",
                                          "C": "It improves hearing", "D": "It replaces exercise"}}}},
        {"text": "Second passage discusses how city trees reduce heat.",
         "questions": {"51": {"stem": "What do city trees reduce?", "answer": "D",
                              "options": {"A": "Rain", "B": "Traffic", "C": "Noise", "D": "Heat"}}}},
    ]}}


def test_section_c_safe_view_selects_own_passage_and_copies_options():
    paper = _section_c_paper()
    first = get_practice_item(paper, 46)
    second = get_practice_item(paper, 51)
    assert first == {"question_number": 46,
                     "passage_text": "First passage explains why sleep helps memory.",
                     "stem": "Why is sleep useful?",
                     "options": {"A": "It saves money", "B": "It helps memory",
                                 "C": "It improves hearing", "D": "It replaces exercise"}}
    assert second["passage_text"] == "Second passage discusses how city trees reduce heat."
    assert "answer" not in first
    first["options"]["B"] = "changed"
    assert paper["section_c"]["passages"][0]["questions"]["46"]["options"]["B"] == "It helps memory"


def test_section_c_grade_uses_keys_and_only_accepts_a_to_d():
    paper = _section_c_paper()
    assert grade_attempt(paper, 46, " b ") == {"submitted": "B", "answer": "B", "correct": True}
    assert grade_attempt(paper, 51, "A") == {"submitted": "A", "answer": "D", "correct": False}
    for submitted in ("", "E", "AA", "?"):
        assert grade_attempt(paper, 46, submitted) is None


def test_section_c_rejects_missing_or_ambiguous_evidence():
    paper = _section_c_paper()
    paper["section_c"]["passages"][0]["text"] = ""
    assert get_practice_item(paper, 46) is None
    paper = _section_c_paper()
    del paper["section_c"]["passages"][0]["questions"]["46"]["options"]["D"]
    assert grade_attempt(paper, 46, "B") is None
    paper = _section_c_paper()
    paper["section_c"]["passages"][0]["questions"]["46"]["answer"] = "E"
    assert get_practice_item(paper, 46) is None
    paper = _section_c_paper()
    paper["section_c"]["passages"][1]["questions"]["46"] = (
        paper["section_c"]["passages"][0]["questions"]["46"].copy()
    )
    assert get_practice_item(paper, 46) is None
    assert grade_attempt(paper, 46, "B") is None


def test_cloze_safe_view_and_keys_grade():
    paper = _cloze_paper()
    item = get_practice_item(paper, 26)
    assert set(item) == {"question_number", "practice_text", "words"}
    assert item["practice_text"].count("{{26}}") == 1
    assert "answer" not in str(item)
    item["words"]["A"] = "changed"
    assert paper["section_a"]["words"]["A"] == "worda"
    assert grade_attempt(paper, 26, " a ") == {
        "submitted": "A", "answer": "A", "correct": True, "answer_word": "worda",
    }
    assert grade_attempt(paper, 26, "B")["correct"] is False
    assert grade_attempt(paper, 26, "S") is None
    assert get_practice_item(paper, 25) is None


def test_cloze_rejects_unverified_data():
    paper = _cloze_paper()
    paper["section_a"]["practice_text"] = paper["section_a"]["practice_text"].replace("{{28}}", "{{27}}")
    assert get_practice_item(paper, 26) is None
    assert grade_attempt(paper, 26, "A") is None
    paper = _cloze_paper()
    paper["section_a"]["questions"]["30"]["answer_word"] = "wrong"
    assert get_practice_item(paper, 26) is None
    paper = _cloze_paper()
    paper["section_a"]["words"].pop("O")
    assert get_practice_item(paper, 26) is None


def test_practice_item_omits_answer_and_keeps_all_candidate_paragraphs():
    paper = _paper()
    item = get_practice_item(paper, 36)
    assert item == {
        "question_number": 36,
        "stem": "A clue",
        "paragraphs": {"A": "First paragraph", "C": "Correct paragraph"},
    }
    assert "answer" not in item
    item["paragraphs"]["C"] = "changed"
    assert paper["paragraphs"]["C"] == "Correct paragraph"


def test_practice_item_rejects_ungradable_or_out_of_range_question():
    paper = _paper()
    assert get_practice_item(paper, 35) is None
    paper["questions"]["36"]["answer"] = "D"
    assert get_practice_item(paper, 36) is None


def test_practice_item_rejects_malformed_stem_without_exposing_cache():
    paper = _paper()
    paper["questions"]["36"]["stem"] = ["bad OCR field"]
    assert get_practice_item(paper, 36) is None


def test_practice_item_rejects_malformed_question_collection():
    paper = _paper()
    paper["questions"] = ["bad OCR section"]
    assert get_practice_item(paper, 36) is None


def test_grade_attempt_uses_keys_and_normalizes_letter():
    paper = _paper()
    assert grade_attempt(paper, 36, " c ") == {
        "submitted": "C", "answer": "C", "correct": True,
    }
    assert grade_attempt(paper, 36, "a") == {
        "submitted": "A", "answer": "C", "correct": False,
    }


def test_grade_attempt_rejects_invalid_answer_or_missing_key():
    paper = _paper()
    for submitted in ("", "S", "AA", "?"):
        assert grade_attempt(paper, 36, submitted) is None
    paper["questions"]["36"].pop("answer")
    assert grade_attempt(paper, 36, "A") is None


def _attempt(qnum, correct):
    return {
        "stage": "attempt_correct" if correct else "attempt_wrong",
        "attempt_answer": "C" if correct else "A",
        "attempt_correct": correct,
        "filters": {"question_number": qnum},
    }


def test_summarize_attempts_ignores_questions_and_counts_repeated_misses():
    events = [
        {"stage": "explanation", "answer_mentioned": "A", "answer_agrees": False},
        _attempt(36, False), _attempt(36, False),
        _attempt(41, True), _attempt(45, False),
    ]
    summary = summarize_attempts(events)
    assert summary["attempt_count"] == 4
    assert summary["correct_count"] == 1
    assert summary["accuracy"] == 0.25
    assert summary["recent_accuracy"] == 0.25
    assert summary["by_range"] == {
        "26-35": {"attempts": 0, "correct": 0},
        "36-40": {"attempts": 2, "correct": 0},
        "41-45": {"attempts": 2, "correct": 1},
        "46-50": {"attempts": 0, "correct": 0},
        "51-55": {"attempts": 0, "correct": 0},
    }
    assert summary["repeated_misses"] == [36]
    assert summary["tier"] == "weakness_snapshot"


def test_cloze_attempts_have_their_own_group():
    summary = summarize_attempts([_attempt(26, False), _attempt(27, True), _attempt(36, True)])
    assert summary["by_range"] == {
        "26-35": {"attempts": 2, "correct": 1},
        "36-40": {"attempts": 1, "correct": 1},
        "41-45": {"attempts": 0, "correct": 0},
        "46-50": {"attempts": 0, "correct": 0},
        "51-55": {"attempts": 0, "correct": 0},
    }


def test_section_c_attempts_have_separate_passage_groups():
    summary = summarize_attempts([_attempt(26, True), _attempt(36, False),
                                  _attempt(46, False), _attempt(51, True)])
    assert summary["by_range"]["46-50"] == {"attempts": 1, "correct": 0}
    assert summary["by_range"]["51-55"] == {"attempts": 1, "correct": 1}
    assert summary["by_range"]["36-40"] == {"attempts": 1, "correct": 0}
    assert summary["tier"] == "weakness_snapshot"


def test_recent_accuracy_uses_last_five_attempts():
    summary = summarize_attempts([_attempt(36, False)] * 5 + [_attempt(41, True)])
    assert summary["attempt_count"] == 6
    assert summary["accuracy"] == 1 / 6
    assert summary["recent_accuracy"] == 0.2


def test_practice_tier_boundaries():
    for count, expected in (
        (0, "plan_insufficient_data"),
        (2, "plan_insufficient_data"),
        (3, "weakness_snapshot"),
        (7, "weakness_snapshot"),
        (8, "session_review"),
    ):
        assert summarize_attempts([_attempt(36, True)] * count)["tier"] == expected


def test_service_records_each_attempt_without_changing_chat_location(tmp_path):
    service = service_module.Service(config=None, session_id="practice-test", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("practice-test", out_dir=str(tmp_path))
    service.table.update({"year": 2020, "month": 7, "exam_set": 1, "question_number": 49})
    before = service.table.to_dict()
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        item = service.practice_question(2024, 12, 1, 36)
        assert item["stem"] == "A clue"
        assert "answer" not in item
        first = service.submit_practice_answer(2024, 12, 1, 36, "a")
        second = service.submit_practice_answer(2024, 12, 1, 36, "c")
    assert service.table.to_dict() == before
    assert first["correct"] is False and first["answer"] == "C"
    assert second["correct"] is True and second["answer"] == "C"
    rows = service.episode.lines()
    assert len(rows) == 2
    assert [row["stage"] for row in rows] == ["attempt_wrong", "attempt_correct"]
    assert [row["attempt_answer"] for row in rows] == ["A", "C"]
    assert [row["attempt_correct"] for row in rows] == [False, True]
    assert all(row["answer_agrees"] is None for row in rows)
    assert all(row["filters"] == {
        "year": 2024, "month": 12, "exam_set": 1, "question_number": 36,
    } for row in rows)
    assert first["trace_id"] != second["trace_id"]
    assert service.practice_progress()["attempt_count"] == 2


def test_practice_persists_keys_grade_across_service_instances(tmp_path):
    path = tmp_path / "learning.jsonl"
    first = service_module.Service(config=None, session_id="first", learning_path=path)
    first.episode = Episode("first", out_dir=str(tmp_path))
    first.table.update({"year": 2020, "month": 7, "exam_set": 1, "question_number": 49})
    before = first.table.to_dict()
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        assert first.practice_question(2024, 12, 1, 36)["stem"] == "A clue"
        wrong = first.submit_practice_answer(2024, 12, 1, 36, "A")
        right = first.submit_practice_answer(2024, 12, 1, 36, "C")
        assert first.submit_practice_answer(2024, 12, 1, 36, "?") is None
    assert first.table.to_dict() == before
    assert wrong["saved"] is True and right["saved"] is True
    assert wrong["event_id"] != right["event_id"]
    reopened = service_module.Service(config=None, session_id="second", learning_path=path)
    assert reopened.practice_progress()["attempt_count"] == 2
    assert reopened.practice_progress()["correct_count"] == 1
    assert reopened.practice_progress()["history_warnings"] == []
    assert reopened.episode.lines() == []


def test_practice_save_failure_keeps_keys_grade(tmp_path):
    service = service_module.Service(config=None, learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("save-failure", out_dir=str(tmp_path))
    with (patch.object(service_module, "load_set_cached_only", return_value=_paper()),
          patch.object(service.learning_record, "append", side_effect=PermissionError("blocked"))):
        result = service.submit_practice_answer(2024, 12, 1, 36, "C")
    assert result["answer"] == "C" and result["correct"] is True
    assert result["saved"] is False and result["event_id"] is None
    assert service.practice_progress()["attempt_count"] == 0


def test_service_rejects_ungradable_submissions_without_recording(tmp_path):
    service = service_module.Service(config=None, session_id="practice-invalid", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("practice-invalid", out_dir=str(tmp_path))
    with patch.object(service_module, "load_set_cached_only", return_value=_paper()):
        assert service.submit_practice_answer(2024, 12, 1, 36, "?") is None
        assert service.submit_practice_answer(2024, 12, 1, 35, "A") is None
    with patch.object(service_module, "load_set_cached_only", return_value=None):
        assert service.practice_question(2024, 12, 1, 36) is None
        assert service.submit_practice_answer(2024, 12, 1, 36, "A") is None
    assert service.episode.lines() == []


def test_cloze_service_records_once_and_gives_non_model_feedback(tmp_path):
    service = service_module.Service(config=None, session_id="cloze-practice", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("cloze-practice", out_dir=str(tmp_path))
    service.table.update({"year": 2024, "month": 6, "exam_set": 1, "question_number": 43})
    before = service.table.to_dict()
    with (
        patch.object(service_module, "load_set_cached_only", return_value=_cloze_paper()),
        patch.object(service_module, "AnswerGeneration", side_effect=AssertionError("LLM called")),
    ):
        item = service.practice_question(2021, 12, 1, 26)
        assert "answer" not in str(item)
        assert service.submit_practice_answer(2021, 12, 1, 26, "S") is None
        attempt = service.submit_practice_answer(2021, 12, 1, 26, "B")
        assert "worda" in service.practice_feedback(attempt["trace_id"])
    assert service.table.to_dict() == before
    assert attempt["answer"] == "A" and attempt["answer_word"] == "worda"
    assert len(service.episode.lines()) == 1
    assert service.practice_progress()["by_range"]["26-35"] == {"attempts": 1, "correct": 0}


def test_section_c_feedback_uses_its_own_passage_without_changing_grade(tmp_path):
    service = service_module.Service(config=None, session_id="section-c-feedback", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("section-c-feedback", out_dir=str(tmp_path))
    service.table.update({"year": 2024, "month": 6, "exam_set": 1, "question_number": 43})
    before = service.table.to_dict()
    seen = []

    class FakeGeneration:
        def __init__(self, config):
            pass

        def generate_section_c_practice_feedback(self, evidence, result, progress):
            seen.append((evidence, result, progress))
            return "原文说树木降低热量；先回到原文定位关键词。"

    with (patch.object(service_module, "load_set_cached_only", return_value=_section_c_paper()),
          patch.object(service_module, "AnswerGeneration", FakeGeneration)):
        attempt = service.submit_practice_answer(2024, 12, 1, 51, "A")
        feedback = service.practice_feedback(attempt["trace_id"])
    assert attempt["answer"] == "D" and attempt["correct"] is False
    assert "参考解析（非官方）" in feedback and "树木降低热量" in feedback
    assert len(seen) == 1
    evidence, result, progress = seen[0]
    assert "Second passage discusses how city trees reduce heat." in evidence
    assert "First passage explains" not in evidence
    assert result == {"submitted": "A", "answer": "D", "correct": False}
    assert progress["by_range"]["51-55"] == {"attempts": 1, "correct": 0}
    assert len(service.episode.lines()) == 1 and service.table.to_dict() == before


@pytest.mark.parametrize("model_text", ["", "标准答案是 A，因为别的选项不对。",
                                        "第46题选 A，因为别的选项不对。", RuntimeError("offline")])
def test_section_c_feedback_downgrades_unusable_model_output(tmp_path, model_text):
    service = service_module.Service(config=None, session_id="section-c-fallback", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("section-c-fallback", out_dir=str(tmp_path))

    class FakeGeneration:
        def __init__(self, config):
            pass

        def generate_section_c_practice_feedback(self, evidence, result, progress):
            if isinstance(model_text, Exception):
                raise model_text
            return model_text

    with (patch.object(service_module, "load_set_cached_only", return_value=_section_c_paper()),
          patch.object(service_module, "AnswerGeneration", FakeGeneration)):
        attempt = service.submit_practice_answer(2024, 12, 1, 46, "A")
        feedback = service.practice_feedback(attempt["trace_id"])
    assert "解析暂不可用" in feedback
    assert "标准答案是 B" in feedback
    assert service.episode.lines()[0]["attempt_correct"] is False
    assert len(service.episode.lines()) == 1


def test_practice_feedback_uses_only_recorded_attempt_and_one_model_call(tmp_path):
    service = service_module.Service(config=None, session_id="feedback-test", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("feedback-test", out_dir=str(tmp_path))
    calls = []

    class FakeGeneration:
        def __init__(self, config):
            pass

        def generate_practice_feedback(self, evidence, result, progress):
            calls.append((evidence, result, progress))
            return "这道题要对应题干关键词；下一题先找同义改写。"

    with (
        patch.object(service_module, "load_set_cached_only", return_value=_paper()),
        patch.object(service_module, "AnswerGeneration", FakeGeneration),
    ):
        attempt = service.submit_practice_answer(2024, 12, 1, 36, "A")
        text = service.practice_feedback(attempt["trace_id"])
    assert "同义改写" in text
    assert len(calls) == 1
    evidence, result, progress = calls[0]
    assert "[答案(KEYS)]C" in evidence
    assert "[用户问的段落A]" in evidence
    assert result == {"submitted": "A", "answer": "C", "correct": False}
    assert progress["attempt_count"] == 1
    assert progress["tier"] == "plan_insufficient_data"
    assert len(service.episode.lines()) == 1


def test_section_b_practice_feedback_rejects_conflicting_model_answer(tmp_path):
    service = service_module.Service(config=None, session_id="b-conflict", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("b-conflict", out_dir=str(tmp_path))

    class FakeGeneration:
        def __init__(self, config):
            pass

        def generate_practice_feedback(self, evidence, result, progress):
            return "正确答案应该是 A，因为别的段落不对。"

    with (patch.object(service_module, "load_set_cached_only", return_value=_paper()),
          patch.object(service_module, "AnswerGeneration", FakeGeneration)):
        attempt = service.submit_practice_answer(2024, 12, 1, 36, "A")
        feedback = service.practice_feedback(attempt["trace_id"])
    assert attempt["answer"] == "C"
    assert "正确答案应该是 A" not in feedback
    assert "KEYS 答案是 C" in feedback


def test_practice_feedback_falls_back_without_changing_grade(tmp_path):
    service = service_module.Service(config=None, session_id="feedback-failure", learning_path=tmp_path / "learning.jsonl")
    service.episode = Episode("feedback-failure", out_dir=str(tmp_path))

    class BrokenGeneration:
        def __init__(self, config):
            pass

        def generate_practice_feedback(self, evidence, result, progress):
            raise RuntimeError("model unavailable")

    with (
        patch.object(service_module, "load_set_cached_only", return_value=_paper()),
        patch.object(service_module, "AnswerGeneration", BrokenGeneration),
    ):
        attempt = service.submit_practice_answer(2024, 12, 1, 36, "C")
        assert "记录还少" in service.practice_feedback(attempt["trace_id"])
        assert "找不到" in service.practice_feedback("unknown-trace")
    row = service.episode.lines()[0]
    assert row["answer_keys"] == "C"
    assert row["attempt_correct"] is True
    assert service.practice_progress()["attempt_count"] == 1


def test_generation_passes_recorded_facts_to_one_plain_model_call():
    prompts = []

    def respond(prompt):
        prompts.append(prompt.to_string())
        return AIMessage(content="先找题干与原文的同义改写。")

    generator = AnswerGeneration.__new__(AnswerGeneration)
    generator.llm = RunnableLambda(respond)
    text = generator.generate_practice_feedback(
        "[答案(KEYS)]C", {"submitted": "A", "answer": "C", "correct": False},
        {"attempt_count": 1, "tier": "plan_insufficient_data"},
    )
    assert text == "先找题干与原文的同义改写。"
    assert len(prompts) == 1
    assert "[答案(KEYS)]C" in prompts[0]
    assert '"submitted": "A"' in prompts[0]
    assert "plan_insufficient_data" in prompts[0]
