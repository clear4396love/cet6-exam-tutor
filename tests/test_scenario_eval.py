import os  # 计算项目根。
import sys  # 补导入路径。


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import tools.scenario_eval as scenario_eval
from tools.scenario_eval import (
    CASES, PRACTICE_CASES, _observe_reply, run_practice_case, score_step, sections_present,
)


def test_observe_reply_recognizes_fill_blank_answer_format():
    expect = {"stage": "answer", "reply_answer": "O"}
    coord = (2024, 12, 1, 26)
    assert _observe_reply(expect, coord, "第26空选 O,填 thrifty。", "O") == "O"
    assert _observe_reply(expect, coord, "第26空选 B,填 thrifty。", "O") is None


def test_resolve_reads_section_a_answer_from_nested_cache(monkeypatch):
    monkeypatch.setattr(
        scenario_eval,
        "load_set",
        lambda *_: {
            "section_a": {
                "questions": {"26": {"answer": "O", "answer_word": "thrifty"}},
                "words": {"O": "thrifty"},
            }
        },
    )
    expect, keys = scenario_eval._resolve(
        {"answer_keys": scenario_eval.KEYS}, (2024, 12, 1, 26)
    )
    assert keys == "O"
    assert expect["answer_keys"] == "O"


def test_section_a_scenario_covers_lookup_follow_up_and_explanation_boundary():
    case = next(case for case in CASES if case["id"] == 13)
    assert [step[0] for step in case["steps"]] == [
        "2024年12月第1套第26题填什么",
        "那27题呢",
        "为什么填这个词？",
    ]
    assert [step[2]["stage"] for step in case["steps"]] == [
        "answer", "answer", "unsupported_type"
    ]
    assert case["steps"][1][2]["state_op"] == "PATCH"
    assert case["steps"][2][2]["answer_keys"] is None


def test_sections_present():
    """八节完整率:数 8 个标题命中了几个。空返回是 0,齐全才是 8。"""
    full = (
        "**题目陷阱分类**\nA\n**相关原文截取**\nB\n**中文参考翻译**\nC\n**完整题目**\nD\n"
        "**题干在问什么**\nE\n**其他段落为什么不匹配**\nF\n**为什么选I**\nG\n**本题复盘**\nH"
    )
    assert sections_present(full) == 8
    assert sections_present("") == 0
    assert sections_present(None) == 0
    # 截断的工况:**只有前 3 节** —— 这正是上一轮 UNPARSEABLE 里的真实形状。
    assert sections_present("**题目陷阱分类**\nA\n**相关原文截取**\nB\n**中文参考翻译**\nC") == 3


def test_score_step_all_pass():
    """全中必须返回空列表 —— 空列表才是"这一步通过"。"""
    assert score_step(
        {"intent": "FOLLOW_UP", "state_op": "PATCH", "stage": "explanation"},
        {"intent": "FOLLOW_UP", "state_op": "PATCH", "stage": "explanation"},
    ) == []


def test_score_step_names_the_mismatch():
    """不符时返回**字段名**,不是布尔 —— 汇总要按项数,失败要能一眼看出败在哪项。"""
    assert score_step(
        {"intent": "FOLLOW_UP", "state_op": "PATCH", "stage": "answer"},
        {"intent": "NEW_QUESTION", "state_op": "PATCH", "stage": "explanation"},
    ) == ["intent", "stage"]


def test_score_step_expected_absent_means_unspecified():
    """期望里没写的字段 = 不检查;但**期望写了 None 就要检查**,两者不能混。

    降级/闲聊那几步的 answer_keys 期望就是 None —— 那是"确定没有答案字母"这个事实,
    不是"没什么可查的"。用 .get() 比对会把"字段缺失"和"值就是 None"混成一个。
    """
    assert score_step({"stage": "not_related"}, {"stage": "not_related", "intent": "NEW_QUESTION"}) == []
    # 期望 None、actual 里键都不存在 → 判不符(系统压根没写这个字段)
    assert score_step({"answer_keys": None}, {}) == ["answer_keys"]
    # 期望 None、actual 真的写了 None → 通过
    assert score_step({"answer_keys": None}, {"answer_keys": None}) == []


def test_practice_cases_cover_submission_tier_boundaries():
    case = PRACTICE_CASES[0]
    assert case["steps"][0]["action"] == "view"
    tiers = [step["expect"]["tier"] for step in case["steps"] if "tier" in step["expect"]]
    assert tiers[0] == "plan_insufficient_data"
    assert "weakness_snapshot" in tiers
    assert tiers[-1] == "session_review"


def test_cloze_practice_case_covers_safe_view_and_keys_grading(tmp_path, monkeypatch):
    case = next(case for case in PRACTICE_CASES if case["id"] == 3)
    rows = run_practice_case(case, str(tmp_path))
    assert [row["failed"] for row in rows] == [[], [], []]
    assert rows[0]["actual"]["answer_hidden"] is True
    assert rows[1]["actual"]["correct"] is False
    assert rows[2]["actual"]["correct"] is True


def test_section_c_practice_case_uses_real_two_passage_cache(tmp_path):
    case = next(case for case in PRACTICE_CASES if case["id"] == 4)
    rows = run_practice_case(case, str(tmp_path))
    assert [row["failed"] for row in rows] == [[]] * len(rows)
    assert rows[0]["actual"]["answer_hidden"] is True
    assert rows[2]["actual"]["answer_hidden"] is True
    assert [row["actual"]["attempt_count"] for row in rows] == [0, 1, 1, 2, 2]
    assert rows[1]["actual"]["correct"] is False
    assert rows[3]["actual"]["correct"] is True


def test_practice_runner_uses_one_real_service_and_never_calls_model(tmp_path, monkeypatch):
    import retrieval.service as service_module

    paper = {
        "questions": {"36": {"stem": "A clue", "answer": "C"}},
        "paragraphs": {"A": "Distractor", "C": "Correct paragraph"},
    }
    monkeypatch.setattr(service_module, "load_set_cached_only", lambda *_: paper)

    class NoModel:
        def __init__(self, config):
            raise AssertionError("practice scenario must not invoke an LLM")

    monkeypatch.setattr(service_module, "AnswerGeneration", NoModel)
    case = {"id": 99, "name": "offline", "steps": [
        {"action": "view", "coord": (2024, 12, 1, 36),
         "expect": {"answer_hidden": True, "attempt_count": 0}},
        {"action": "submit", "coord": (2024, 12, 1, 36), "submitted": "A",
         "expect": {"stage": "attempt_wrong", "answer_keys": "C", "correct": False,
                    "attempt_count": 1, "tier": "plan_insufficient_data"}},
        {"action": "submit", "coord": (2024, 12, 1, 36), "submitted": "C",
         "expect": {"stage": "attempt_correct", "answer_keys": "C", "correct": True,
                    "attempt_count": 2, "tier": "plan_insufficient_data"}},
    ]}
    rows = run_practice_case(case, str(tmp_path))
    assert [row["failed"] for row in rows] == [[], [], []]
    assert [row["actual"]["attempt_count"] for row in rows] == [0, 1, 2]


def test_practice_runner_isolates_each_case_ledger(tmp_path, monkeypatch):
    import retrieval.service as service_module

    monkeypatch.setattr(service_module, "load_set_cached_only", lambda *_: {
        "questions": {"36": {"stem": "A clue", "answer": "C"}},
        "paragraphs": {"A": "Distractor", "C": "Correct paragraph"},
    })
    case = {"id": 100, "name": "one submission", "steps": [
        {"action": "submit", "coord": (2024, 12, 1, 36), "submitted": "C",
         "expect": {"attempt_count": 1, "correct": True}},
    ]}
    first = run_practice_case(case, str(tmp_path))
    case["id"] = 101
    second = run_practice_case(case, str(tmp_path))
    assert first[0]["failed"] == second[0]["failed"] == []


def test_draft_scenario_uses_real_cache_and_restores_pending_draft(tmp_path):
    case = next(item for item in scenario_eval.DRAFT_CASES if item["id"] == 5)
    rows = scenario_eval.run_draft_case(case, str(tmp_path))
    assert [row["failed"] for row in rows] == [[], [], []]
    assert rows[0]["actual"]["sample_hidden"] is True
    assert rows[1]["actual"]["status"] == "saved"
    assert rows[2]["actual"]["latest_feedback_status"] == "pending"


if __name__ == "__main__":
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"\n全部通过 ✅({len(tests)} 个)")
