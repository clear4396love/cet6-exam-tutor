import os
import sys
import tempfile
from contextlib import ExitStack
from unittest.mock import patch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from memory.episode import Episode
import retrieval.service as service_module
# 复用上一轮已有的假件,不重复造。
from tests.test_state_and_trace import (
    FAKE_PAPER,
    FakeAnswerGeneration,
    FakeFindIntent,
)

# ★ 期望值独立写死 —— 不从 retrieval.service import 常量。
# 否则产品文案被改坏时测试跟着一起变,契约就守不住了;
# 而且改之前会先吃 ImportError,看不到真正的行为失败。
DEGRADE_PREFIX = "【未定位到原题】"
DUPLICATE_PREFIX = "【重复阅读题未单独收录】"
UNSUPPORTED_PREFIX = "【当前题型未支持】"

# 套在、题号也在,但 answer 是 None —— 单独触发“缺 KEYS”。
PAPER_NO_ANSWER = {
    "year": 2024, "month": 11, "exam_set": 1,
    "paragraphs": {"A": "Paragraph A evidence."},
    "questions": {"43": {"stem": "Question 43", "answer": None}},
}

# 套在,但 36~45 一个题号都没有 —— 模拟“原因不明的空数据”(异常,要查)。
# 注意:那 5 套**已知重复**的走的是 duplicate_section,在这条检查之前就返回了,
# 所以这条覆盖的是名单之外的异常空 B 段,真实库里当前不可达。
PAPER_NO_SECTION_B = {
    "year": 2024, "month": 11, "exam_set": 2,
    "paragraphs": {"A": "Paragraph A evidence."},
    "questions": {"26": {"stem": "Question 26", "answer": "A"}},
}

# 套在、B 段在,但第 43 题这一条没有 —— 触发 cache_miss_question。
# 真实库里也不可达(33 套全是 10/10),只能靠假数据覆盖。
PAPER_PARTIAL_B = {
    "year": 2024, "month": 11, "exam_set": 3,
    "paragraphs": {"A": "Paragraph A evidence."},
    "questions": {
        "36": {"stem": "Question 36", "answer": "A"},
        "45": {"stem": "Question 45", "answer": "A"},
    },
}

# Section A 有数据,但答案单词与词库对不上(缓存不可信) → 必须降级,不许猜。
# 套数只能是 1~3(locator.py 的 sanitize_position 会钳),所以别用第 4 套当坐标。
PAPER_SECTION_A_MISMATCH = {
    "year": 2024, "month": 12, "exam_set": 2,
    "paragraphs": {"A": "Paragraph A evidence."},
    "questions": {"36": {"stem": "Question 36", "answer": "A"}},
    "section_a": {
        "q_from": 26, "q_to": 35,
        "words": {"A": "alpha", "O": "thrifty"},
        "questions": {"26": {"answer": "A", "answer_word": "beta"}},
    },
}


def fake_load_set(year, month, exam_set):
    """只有这里列出的五套存在,其余一律 None(等于库外)。"""
    if (year, month, exam_set) == (2024, 12, 1):
        return FAKE_PAPER
    if (year, month, exam_set) == (2024, 12, 2):
        return PAPER_SECTION_A_MISMATCH
    if (year, month, exam_set) == (2024, 11, 1):
        return PAPER_NO_ANSWER
    if (year, month, exam_set) == (2024, 11, 2):
        return PAPER_NO_SECTION_B
    if (year, month, exam_set) == (2024, 11, 3):
        return PAPER_PARTIAL_B
    return None


def _run(inputs, real_loaders=False):
    """在同一个会话里按顺序跑一串输入,返回 (回答列表, 轨迹行列表)。

    两条数据路各有一个按名字可 patch 的入口,所以替换件也要挂两份:
    load_set(段落匹配 36~45 用)和 load_set_cached_only(Section A 用的只读版)。
    real_loaders=True 时两个都换成真的 —— 只有「缺缓存不写盘」那条用例需要,
    它要证明的就是「真的走了一遍也没写文件」。
    """
    with tempfile.TemporaryDirectory(prefix="degrade_test_") as tmp:
        app = service_module.Service(config=None, session_id="degrade")
        app.episode = Episode("degrade", out_dir=tmp)
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(service_module, "Find_Intent", FakeFindIntent)
            )
            stack.enter_context(
                patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration)
            )
            if not real_loaders:
                stack.enter_context(
                    patch.object(service_module, "load_set", side_effect=fake_load_set)
                )
                stack.enter_context(
                    patch.object(service_module, "load_set_cached_only",
                                 side_effect=fake_load_set)
                )
            answers = [app.process(q) for q in inputs]
        return answers, app.episode.lines()


def test_degrade_contract():
    """各降级出口 / 8 种 stage / 10 个场景:首行都带标记,out_of_library 分得清。

    除作文那行外,每行都带卷级锚点 → state_op_of 必然 RESET(intent.py:65);
    作文那行只有 section、没有卷级锚点,走的是默认 RESET(intent.py:77)。
    两条路都不继承上一轮的卷,所以用例之间不串状态,可以任意调序。
    """
    cases = [
        # 输入,                          预期 stage,            预期 ool, 预期前缀,            必含文案
        ("2024年11月第1套怎么复习",        "missing_question",   False, DEGRADE_PREFIX,     "2024年11月第1套的哪一道题"),
        ("作文怎么提高",                  "unsupported_type",   True,  UNSUPPORTED_PREFIX, None),
        ("2024年12月第1套答案",            "unsupported_type",   True,  UNSUPPORTED_PREFIX, None),
        ("2024年第43题选什么",            "missing_paper",      False, DEGRADE_PREFIX,     None),
        # ★ 第 26 题以前是 unsupported_type(整个题型没上线);选词填空查答案上线后,
        # 这句该 FAIL 的坐标换成 Section A 自己的缺数据出口(答案与词库对不上)。
        ("2024年12月第2套第26题填什么",    "cache_miss_section", True,  DEGRADE_PREFIX,     None),
        ("2029年12月第1套第43题选什么",    "cache_miss_paper",   True,  DEGRADE_PREFIX,     None),
        # ★ 用真实名单里的坐标,不 patch 常量 —— 名单是业务规则,不是测试夹具。
        # 它在 load_set() 之前返回,不读也不写真实缓存。
        ("2022年9月第2套第43题选什么",    "duplicate_section",  True,  DUPLICATE_PREFIX,   "与同场次其他套重复"),
        ("2024年11月第2套第43题选什么",    "cache_miss_section", True,  DEGRADE_PREFIX,     None),
        ("2024年11月第3套第43题选什么",    "cache_miss_question",True,  DEGRADE_PREFIX,     None),
        ("2024年11月第1套第43题选什么",    "cache_miss_answer",  True,  DEGRADE_PREFIX,     None),
    ]
    answers, rows = _run([q for q, *_ in cases])

    for (q, stage, ool, prefix, must), text, row in zip(cases, answers, rows):
        assert text.startswith(prefix), f"{q}: 首行没带标记 -> {text[:40]}"
        if must:
            # 卷已经说全了,就不许再让用户重说年月套。
            assert must in text, f"{q}: 回复没接住已给的定位 -> {text[:60]}"
        assert row["stage"] == stage, f"{q}: stage={row['stage']} 期望 {stage}"
        assert row["out_of_library"] is ool, f"{q}: out_of_library={row['out_of_library']}"
        assert row["hit"] is False, f"{q}: 没答上来的轮次 hit 必须是 False"


def test_normal_answer_is_not_labeled():
    """反向契约:真答上来了就不许带任何降级标记 —— 否则标记本身失去意义。"""
    answers, rows = _run(["2024年12月第1套第43题选什么"])

    # startswith 收元组:三个前缀都要排,漏一个就等于允许正常答案误挂降级标记。
    assert not answers[0].startswith(
        (DEGRADE_PREFIX, DUPLICATE_PREFIX, UNSUPPORTED_PREFIX)
    )
    assert rows[0]["stage"] == "answer"
    assert rows[0]["hit"] is True
    assert rows[0]["out_of_library"] is False


def test_section_a_answer_lookup_and_followup():
    """查答案 + 追问下一空:答案以缓存为准,两轮都不带降级标记。"""
    answers, rows = _run(["2024年12月第1套第26题填什么", "那27题呢"])

    for text in answers:
        assert not text.startswith(
            (DEGRADE_PREFIX, DUPLICATE_PREFIX, UNSUPPORTED_PREFIX)
        ), text[:40]
    assert "第26空选 O,填 thrifty" in answers[0]
    assert "第27空选 A,填 discouraging" in answers[1]

    assert rows[0]["stage"] == "answer"
    assert rows[0]["hit"] is True and rows[0]["out_of_library"] is False
    assert rows[0]["retrieved_doc_ids"] == ["2024_12_1"]
    assert rows[0]["answer_keys"] == "O"
    # 普通查答案没提字母,三态字段必须保持 None,不能记成 False。
    assert rows[0]["answer_mentioned"] is None
    assert rows[0]["answer_agrees"] is None

    # 追问轮:只给题号也要继承当前卷,而且仍然是答案轮。
    assert rows[1]["state_op"] == "PATCH"
    assert rows[1]["stage"] == "answer"
    assert rows[1]["hit"] is True


def test_section_a_decline():
    """缺 Section A / 数据对不上 → 降级;问讲解 → 明说这个题型不支持讲解。"""
    answers, rows = _run([
        "2024年11月第2套第26题填什么",            # 有段落匹配,没有 section_a
        "2024年12月第2套第26题填什么",            # answer_word 与词库对不上
        "2024年12月第1套第26题为什么填thrifty",    # 解释请求
    ])

    assert rows[0]["stage"] == "cache_miss_section"
    assert answers[0].startswith(DEGRADE_PREFIX)
    assert rows[0]["hit"] is False and rows[0]["out_of_library"] is True

    assert rows[1]["stage"] == "cache_miss_section"
    assert answers[1].startswith(DEGRADE_PREFIX)

    assert rows[2]["stage"] == "unsupported_type"
    assert answers[2].startswith(UNSUPPORTED_PREFIX)
    assert rows[2]["hit"] is False and rows[2]["out_of_library"] is True


def test_section_a_missing_cache_does_not_write():
    """缺缓存只降级,绝不顺手解析 PDF 写盘。

    两个 loader 都换成真的,并把 CACHE_DIR 指到空目录:如果 Section A 被接回
    会写盘的 load_set,(2024,12,1) 的精确同名 PDF 真的在,必然在 tmp 里留下一份 JSON。
    """
    # ★ 要 patch 的是**顶层** paper_parser:structured.py 用的是
    # `from paper_parser import paper`(先插 retrieval/ 进 sys.path),
    # retrieval.paper_parser 在不同导入顺序下是**另一个模块对象**,patch 它没用。
    import paper_parser

    with tempfile.TemporaryDirectory(prefix="no_write_test_") as tmp:
        old = paper_parser.CACHE_DIR
        paper_parser.CACHE_DIR = tmp
        try:
            answers, rows = _run(["2024年12月第1套第26题填什么"], real_loaders=True)
            assert rows[0]["stage"] == "cache_miss_paper"
            assert answers[0].startswith(DEGRADE_PREFIX)
            assert os.listdir(tmp) == []
        finally:
            paper_parser.CACHE_DIR = old


def test_section_c_answer_followup_and_explanation_boundary():
    answers, rows = _run([
        "2020年7月第1套第49题选什么",
        "第50题呢",
        "2020年7月第1套第49题为什么选C",
    ], real_loaders=True)
    assert "第49题选 C" in answers[0]
    assert "It is something everybody has to live with." in answers[0]
    assert rows[0]["stage"] == "answer"
    assert rows[0]["answer_keys"] == "C"
    assert rows[0]["retrieved_doc_ids"] == ["2020_7_1"]
    assert "第50题选 C" in answers[1]
    assert rows[1]["state_op"] == "PATCH"
    assert "离线仔细阅读八节讲解" in answers[2]
    assert rows[2]["stage"] == "explanation"
    assert rows[2]["answer_verified"] is True
    assert rows[2]["answer_keys"] == "C"
    assert rows[2]["hit"] is True


def test_section_c_missing_section_fails_closed():
    answers, rows = _run(["2022年9月第2套第49题选什么"], real_loaders=True)
    assert answers[0].startswith(DEGRADE_PREFIX)
    assert rows[0]["hit"] is False
    assert rows[0]["stage"] == "cache_miss_section"


def test_section_c_explanation_works_across_papers_and_both_passages():
    cases = [
        ("2020年12月第1套第46题为什么选B", "B", "2020_12_1"),
        ("2022年9月第1套第55题为什么选C", "C", "2022_9_1"),
        ("2025年6月第3套第51题为什么选A", "A", "2025_6_3"),
    ]
    replies, rows = _run([question for question, _, _ in cases], real_loaders=True)
    for reply, row, (_, letter, cache_key) in zip(replies, rows, cases):
        assert "离线仔细阅读八节讲解" in reply
        assert row["stage"] == "explanation"
        assert row["answer_verified"] is True
        assert row["answer_keys"] == letter
        assert row["retrieved_doc_ids"] == [cache_key]
        assert row["hit"] is True


def test_section_c_explanation_needs_original_passage():
    paper = {"section_c": {"passages": [{"text": "", "questions": {
        "49": {"stem": "What happened?", "options": {"A": "one", "B": "two", "C": "three", "D": "four"}, "answer": "C"}
    }}]}}
    app = service_module.Service(config=None)
    with patch.object(service_module, "load_set_cached_only", return_value=paper):
        reply = app._multiple_choice_answer(
            {"year": 2024, "month": 12, "exam_set": 1}, 49, "为什么选C"
        )
    assert reply.startswith(DEGRADE_PREFIX)
    assert app._tr["stage"] == "cache_miss_section"
    assert app._tr["hit"] is False


def test_section_c_model_failure_keeps_cached_answer():
    class BrokenGeneration:
        def __init__(self, config, max_tokens=None):
            pass

        def generate_section_c(self, question, context):
            raise ConnectionError("model unavailable")

    app = service_module.Service(config=None)
    with (
        patch.object(service_module, "AnswerGeneration", BrokenGeneration),
        patch.object(service_module, "load_set_cached_only", return_value=service_module.load_set_cached_only(2020, 7, 1)),
    ):
        reply = app._multiple_choice_answer(
            {"year": 2020, "month": 7, "exam_set": 1}, 49, "为什么不选D"
        )
    assert "第49题选 C" in reply
    assert "讲解暂时" in reply
    assert app._tr["answer_keys"] == "C"
    assert app._tr["stage"] == "generation_error"


# 名单是**业务规则**,不是测试夹具:生产代码漏写四套或写错年份,这条必须红。
EXPECTED_DUPLICATE_SECTION_B = {
    (2022, 6, 3),
    (2022, 9, 2),
    (2022, 9, 3),
    (2023, 3, 2),
    (2023, 3, 3),
}


def test_duplicate_section_coordinates():
    """配置契约:锁住那张名单本身。

    别改成“把常量 patch 成假坐标再测行为” —— 那样生产名单漏写四套、年份写错,
    单测照样全绿,锁了个寂寞。
    """
    # getattr + 兜底:常量还没写进 service.py 时,这里是**断言失败**,不是 AttributeError 崩掉。
    assert getattr(service_module, "_SKIPPED_DUPLICATE_SECTION_B", set()) == EXPECTED_DUPLICATE_SECTION_B


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n全部通过 ✅({len(fns)} 个)")
