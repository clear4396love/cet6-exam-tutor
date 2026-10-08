import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from retrieval.locator import (
    parse_conditions,
    sanitize_position,
    unsafe_relative_references,
)


# ---------- parse_conditions:真实例句 ----------

def test_parse_conditions_real_sentences():
    assert parse_conditions("2024年12月第1套翻译讲了什么") == {
        "year": 2024, "month": 12, "exam_set": 1, "section": "translation",
    }
    assert parse_conditions("2024年12月第一套第43题选什么") == {
        "year": 2024, "month": 12, "question_number": 43, "exam_set": 1,
    }
    assert parse_conditions("第一套第42题为什么选A") == {
        "question_number": 42, "exam_set": 1,
    }
    assert parse_conditions("那44题呢") == {"question_number": 44}
    assert parse_conditions("作文怎么提高") == {"section": "writing"}
    assert parse_conditions("为什么选c选项呢") == {}
    assert parse_conditions("你好呀") == {}


def test_question_number_is_not_mistaken_for_exam_set():
    """「第一题」必须走题号，不能被套数正则接走。"""
    assert parse_conditions("第一题选什么") == {"question_number": 1}
    assert parse_conditions("第1题") == {"question_number": 1}


def test_chinese_compound_question_number():
    """「十六」必须读成 16，不是 6。"""
    assert parse_conditions("听力第十六题呢")["question_number"] == 16
    assert parse_conditions("第十一题")["question_number"] == 11
    assert parse_conditions("第二十题")["question_number"] == 20
    assert parse_conditions("第四十五题")["question_number"] == 45
    assert parse_conditions("第十题")["question_number"] == 10


def test_chinese_month_and_exam_set():
    assert parse_conditions("2025年十二月第一套") == {
        "year": 2025,
        "month": 12,
        "exam_set": 1,
    }
    assert parse_conditions("2024年十月第三套第四十五题") == {
        "year": 2024,
        "month": 10,
        "question_number": 45,
        "exam_set": 3,
    }


def test_three_digit_question_number_not_truncated():
    """三位数不许被从后两位误匹配（'第101题' 变成 1）。"""
    assert parse_conditions("第101题")["question_number"] == 101
    assert parse_conditions("第100题")["question_number"] == 100
    assert parse_conditions("第101题").get("question_number") != 1


def test_relative_question_is_not_parsed_as_question_one():
    """相对题号短语不是数字题号：「下一题」绝不能变成第 1 题。"""
    assert parse_conditions("下一题") == {}
    assert parse_conditions("上一题呢") == {}
    assert parse_conditions("前一题") == {}
    assert parse_conditions("后一题") == {}
    # 真·第一题/复合中文数字不能受影响。
    assert parse_conditions("第一题") == {"question_number": 1}
    assert parse_conditions("第十一题") == {"question_number": 11}
    # 同一句里的年月套必须保留，只是不产生假题号。
    assert parse_conditions("2025年12月第1套的下一题") == {
        "year": 2025,
        "month": 12,
        "exam_set": 1,
    }


# ---------- 相对指代:无法安全换算的表达 ----------

def test_unsafe_relative_references_matrix():
    """矩阵:哪些相对表达必须拦、哪些正常追问必须放行。"""
    assert unsafe_relative_references("下一题", {}) == ("下一题",)
    assert unsafe_relative_references("上一题呢", {}) == ("上一题",)
    assert unsafe_relative_references("前一题", {}) == ("前一题",)
    assert unsafe_relative_references("后一题", {}) == ("后一题",)

    # 套数/题号移动词:即使同句已有数字套数或题号也拦 —— 数字只可能是移动基准。
    assert unsafe_relative_references(
        "2025年12月第1套的下一套",
        {"year": 2025, "month": 12, "exam_set": 1},
    ) == ("下一套",)
    assert unsafe_relative_references(
        "2025年今年12月第1套的下一题",
        {"year": 2025, "month": 12, "exam_set": 1},
    ) == ("下一题",)

    # 年份相对词:只有本句没有合法四位年份时才拦。
    assert unsafe_relative_references("去年第44题", {"question_number": 44}) == ("去年",)
    assert unsafe_relative_references(
        "2025年今年12月第1套第44题",
        {"year": 2025, "month": 12, "exam_set": 1, "question_number": 44},
    ) == ()

    # 正常追问/普通指代必须放行。
    assert unsafe_relative_references("这道题", {}) == ()
    assert unsafe_relative_references("那B呢", {}) == ()
    assert unsafe_relative_references("第44题呢", {"question_number": 44}) == ()

    # 一句话命中多个 → 全部返回,不截断。
    assert set(unsafe_relative_references("去年那套的下一题", {})) == {
        "去年", "下一题",
    }


# ---------- sanitize_position:不可信输入 ----------

def test_sanitize_position_rejects_non_dict():
    """模型可能吐数组/字符串/数字；一律降级成空 dict，不许崩。"""
    assert sanitize_position(None) == {}
    assert sanitize_position({}) == {}
    assert sanitize_position("abc") == {}
    assert sanitize_position(123) == {}
    assert sanitize_position(["a"]) == {}
    assert sanitize_position(("x",)) == {}


def test_sanitize_position_rejects_fractions():
    """小数不许被偷偷截断（42.9 不是 42）。"""
    assert sanitize_position({"year": 2024}) == {"year": 2024}
    assert sanitize_position({"year": "2024"}) == {"year": 2024}
    assert sanitize_position({"year": 2024.0}) == {"year": 2024}
    assert sanitize_position({"year": 2024.9}) == {}
    assert sanitize_position({"question_number": 42.0}) == {"question_number": 42}
    assert sanitize_position({"question_number": 42.9}) == {}
    assert sanitize_position({"month": 12.5}) == {}
    assert sanitize_position({"exam_set": 1.7}) == {}


def test_sanitize_position_rejects_bool():
    """Python 里 True 就是 1；模型吐 true 不能变成「第 1 题」。"""
    assert sanitize_position({"question_number": True}) == {}
    assert sanitize_position({"question_number": False}) == {}
    assert sanitize_position({"month": True}) == {}


def test_sanitize_position_clamps_range():
    assert sanitize_position({"month": 13}) == {}
    assert sanitize_position({"month": 0}) == {}
    assert sanitize_position({"exam_set": 0}) == {}
    assert sanitize_position({"exam_set": 4}) == {}
    assert sanitize_position({"question_number": 101}) == {}
    assert sanitize_position({"question_number": 0}) == {}
    assert sanitize_position({"year": 24}) == {}
    assert sanitize_position({"year": 2030}) == {}


def test_sanitize_position_normalizes_section():
    assert sanitize_position({"section": "翻译"}) == {"section": "translation"}
    assert sanitize_position({"section": "  TRANSLATION "}) == {"section": "translation"}
    assert sanitize_position({"section": "作文"}) == {"section": "writing"}
    assert sanitize_position({"section": "不认识的板块"}) == {}


def test_sanitize_position_drops_non_whitelisted():
    """option/paragraph/word 不在白名单，一律丢。"""
    assert sanitize_position(
        {"option": "B", "paragraph": "K", "word": 3, "year": 2024}
    ) == {"year": 2024}


if __name__ == "__main__":
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n全部通过 ✅({len(fns)} 个)")
