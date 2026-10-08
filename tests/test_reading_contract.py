"""Generated reading prose is not trusted to choose an answer or shape its own contract."""

from unittest.mock import patch

import pytest

from retrieval.answer_contract import valid_explanation
from retrieval import service as service_module
from tests.test_state_and_trace import FAKE_PAPER


def _eight_sections(answer="A", section="B"):
    sixth = "其他段落为什么不匹配" if section == "B" else "其他选项为什么不匹配"
    names = ("题目陷阱分类", "相关原文截取", "中文参考翻译", "完整题目",
             "题干在问什么", sixth, f"为什么选{answer}", "本题复盘")
    return "\n".join(f"**{name}**\n具体说明。" for name in names)


@pytest.mark.parametrize("section,answer", [("B", "A"), ("C", "D")])
def test_valid_explanation_accepts_the_correct_section_contract(section, answer):
    assert valid_explanation(_eight_sections(answer, section), section, answer)


@pytest.mark.parametrize("damage", ["missing", "reordered", "duplicate", "wrong_letter",
                                    "contradiction", "question_claim", "modal_claim",
                                    "modal_choice", "emphasis_claim", "reverse_claim",
                                    "lowercase_claim", "adjacent_reverse_claim",
                                    "extra_heading", "empty_section"])
def test_valid_explanation_rejects_damaged_structure_or_answer(damage):
    good = _eight_sections()
    lines = good.splitlines()
    if damage == "missing":
        bad = "\n".join(lines[:-2])
    elif damage == "reordered":
        lines[0], lines[2] = lines[2], lines[0]
        bad = "\n".join(lines)
    elif damage == "duplicate":
        bad = good + "\n**本题复盘**\n重复。"
    elif damage == "wrong_letter":
        bad = good.replace("为什么选A", "为什么选B")
    elif damage == "question_claim":
        bad = good + "\n第43题选 B。"
    elif damage == "modal_claim":
        bad = good + "\n正确答案应该是 B。"
    elif damage == "modal_choice":
        bad = good + "\n所以应该选 B。"
    elif damage == "emphasis_claim":
        bad = good + "\n正确答案其实是 B。"
    elif damage == "reverse_claim":
        bad = good + "\nB 才是正确答案。"
    elif damage == "lowercase_claim":
        bad = good + "\n标准答案是 b。"
    elif damage == "adjacent_reverse_claim":
        bad = good + "\n第43题B才是正确答案。"
    elif damage == "extra_heading":
        bad = good + "\n**补充答案**\nB"
    elif damage == "empty_section":
        bad = good.replace("**相关原文截取**\n具体说明。", "**相关原文截取**\n")
    else:
        bad = good + "\n标准答案是 B。"
    assert not valid_explanation(bad, "B", "A")


def test_section_b_model_conflict_downgrades_without_leaking_prose():
    class Generation:
        def __init__(self, config, max_tokens=None):
            pass

        def generate_structured(self, question, context):
            return _eight_sections("B", "B") + "\n标准答案是 B。"

    service = service_module.Service(config=None, cached_only=True)
    with (patch.object(service_module, "load_set_cached_only", return_value=FAKE_PAPER),
          patch.object(service_module, "AnswerGeneration", Generation)):
        reply = service._structured_answer(
            {"year": 2024, "month": 12, "exam_set": 1, "question_number": 43},
            "第43题为什么选A",
        )
    assert "按 KEYS 选 A" in reply
    assert "标准答案是 B" not in reply
    assert service._tr["stage"] == "generation_invalid"
    assert service._tr["answer_verified"] is False


def test_section_c_valid_and_invalid_explanations_respect_keys():
    paper = {"section_c": {"passages": [{"text": "The passage says so.", "questions": {
        "46": {"stem": "What happened?", "answer": "D",
               "options": {"A": "one", "B": "two", "C": "three", "D": "four"}}
    }}]}}

    class Generation:
        response = _eight_sections("D", "C")

        def __init__(self, config, max_tokens=None):
            pass

        def generate_section_c(self, question, context):
            return self.response

    service = service_module.Service(config=None)
    with (patch.object(service_module, "load_set_cached_only", return_value=paper),
          patch.object(service_module, "AnswerGeneration", Generation)):
        good = service._multiple_choice_answer(
            {"year": 2024, "month": 12, "exam_set": 1}, 46, "第46题为什么选D")
        assert good == Generation.response
        assert service._tr["stage"] == "explanation"
        assert service._tr["answer_verified"] is True

        Generation.response = _eight_sections("B", "C")
        bad = service._multiple_choice_answer(
            {"year": 2024, "month": 12, "exam_set": 1}, 46, "第46题为什么选D")
    assert "第46题按 KEYS 选 D" in bad
    assert "为什么选B" not in bad
    assert service._tr["stage"] == "generation_invalid"
    assert service._tr["answer_verified"] is False
