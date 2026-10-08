# -*- coding: utf-8 -*-
"""structured.py 纯函数单测(不连 LLM、不连 Milvus、不改缓存)。

跑法:
    python -m pytest tests/            (装了 pytest)
    或 python tests/test_structured.py  (自带 assert 直跑)
对 parsed_papers/*.json 只读。
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from retrieval.structured import (
    load_set, load_set_cached_only, get_questions, get_paragraphs, get_question,
    get_answer, get_section_a_answer, get_section_c_question, qtype_of, clean_text, extract_mention_letter,
    wants_explanation, build_evidence,
)
from retrieval import structured as structured_module


def test_qtype_ranges():
    assert qtype_of(26) == qtype_of(35) == "fill_blank"
    assert qtype_of(36) == qtype_of(45) == "paragraph_matching"
    assert qtype_of(46) == qtype_of(55) == "multiple_choice"
    assert qtype_of(10) is None and qtype_of(60) is None


def test_clean_text():
    assert clean_text(")If contributing factors") == "If contributing factors"
    assert clean_text("fantasy。") == "fantasy."
    assert clean_text("  a   b ") == "a b"


def test_extract_mention_letter():
    assert extract_mention_letter("为什么不选 D") == "D"
    assert extract_mention_letter("为什么选K") == "K"
    assert extract_mention_letter("那B呢") == "B"
    assert extract_mention_letter("A段错在哪里？") == "A"
    assert extract_mention_letter("B段哪里不对？") == "B"
    assert extract_mention_letter("这段话在讲什么") is None
    assert extract_mention_letter("我查了原文第45题答案") is None  # 无上下文不误抓


def test_wants_explanation():
    assert wants_explanation("为什么选K")
    assert wants_explanation("为什么不选A")
    assert not wants_explanation("第44题选什么")


def test_flat_accessors():
    flat = {"paragraphs": {"A": "x"}, "questions": {"36": {"stem": "s", "answer": "A"}}}
    assert get_paragraphs(flat) == {"A": "x"}
    assert get_answer(flat, 36) == "A"
    assert get_question(flat, 36) == {"stem": "s", "answer": "A"}
    assert get_question(flat, 99) is None


def test_real_cache_text_layer_2024_12_1():
    d = load_set(2024, 12, 1)
    assert d is not None
    assert sorted(int(k) for k in get_questions(d)) == list(range(36, 46))
    paras = get_paragraphs(d)
    for q in range(36, 46):
        ans = get_answer(d, q)
        assert ans is not None and ans in paras, f"q{q} 答案 {ans} 不在段落里"


def test_evidence_content():
    d = load_set(2024, 12, 1)
    ans45 = get_answer(d, 45)
    wrong = next(l for l in sorted(get_paragraphs(d)) if l != ans45)
    ev = build_evidence(d, 45, wrong)
    assert f"[答案(KEYS)]{ans45}" in ev
    assert f"[原文段落{ans45}]" in ev
    assert f"[用户问的段落{wrong}]" in ev


def test_section_a_answer_from_real_cache():
    """真实缓存里 26~35 十空都能查到,且字母与词库对得上。"""
    d = load_set(2024, 12, 1)
    assert get_section_a_answer(d, 26) == ("O", "thrifty")
    words = d["section_a"]["words"]
    for q in range(26, 36):
        letter, word = get_section_a_answer(d, q)
        assert words[letter] == word, f"第{q}空 {letter}={word} 与词库不符"
    assert get_section_a_answer(d, 43) is None      # 43 属于 Section B,不在这张表里


def test_section_a_rejects_bad_data():
    """缺数据或数据对不上 → None,而不是抛异常。"""
    good = {"words": {"A": "alpha"}, "questions": {"26": {"answer": "A", "answer_word": "alpha"}}}
    assert get_section_a_answer({"section_a": good}, 26) == ("A", "alpha")

    bad = [
        {},                                              # 没 section_a
        {"section_a": None},
        {"section_a": []},
        {"section_a": {"words": {}, "questions": {}}},    # 空表
        {"section_a": {"words": {"A": "alpha"}, "questions": "not a dict"}},
        {"section_a": {"words": ["alpha"], "questions": {"26": {"answer": "A", "answer_word": "alpha"}}}},
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": "not a dict"}}},
        {"section_a": {"words": {"A": "alpha"}, "questions": {"27": {"answer": "A", "answer_word": "alpha"}}}},
        # 答案字母不在词库里
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": {"answer": "B", "answer_word": "beta"}}}},
        # answer_word 和词库对不上
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": {"answer": "A", "answer_word": "beta"}}}},
        # answer / answer_word 是空值
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": {"answer": None, "answer_word": "alpha"}}}},
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": {"answer": "A", "answer_word": None}}}},
        {"section_a": {"words": {"A": "alpha"}, "questions": {"26": {"answer": "A"}}}},
    ]
    for bad_paper in bad:
        assert get_section_a_answer(bad_paper, 26) is None, bad_paper


def test_section_c_question_requires_matching_answer_option():
    question = {
        "stem": "What happened?",
        "options": {"A": "first", "B": "second", "C": "third", "D": "fourth"},
        "answer": "C",
    }
    paper = {"section_c": {"passages": [{"questions": {"49": question}}]}}
    assert get_section_c_question(paper, 49) == ("C", "third")
    assert get_section_c_question(paper, 50) is None
    question["answer"] = "E"
    assert get_section_c_question(paper, 49) is None
    question["answer"] = None
    assert get_section_c_question(paper, 49) is None


def test_section_c_2020_7_1_matches_answer_page():
    paper = load_set_cached_only(2020, 7, 1)
    assert "".join(get_section_c_question(paper, n)[0] for n in range(46, 56)) == "BDACCBCAAC"


def test_section_c_evidence_contains_this_question_passage_options_and_keys():
    assert hasattr(structured_module, "build_section_c_evidence")
    paper = load_set_cached_only(2020, 7, 1)
    evidence = structured_module.build_section_c_evidence(paper, 49)
    assert "[题干]What can be inferred from the passage about day-to-day stress?" in evidence
    assert "[选项C]It is something everybody has to live with." in evidence
    assert "[选项D]It does not help build up one's tolerance." in evidence
    assert "[答案(KEYS)]C" in evidence
    assert "[原文]" in evidence
    assert "day-to-day stress" in evidence
    assert "medical professionals argue" in evidence


def test_section_c_evidence_rejects_missing_passage():
    assert hasattr(structured_module, "build_section_c_evidence")
    paper = {"section_c": {"passages": [{"text": "", "questions": {
        "49": {"stem": "question", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "answer": "C"}
    }}]}}
    assert structured_module.build_section_c_evidence(paper, 49) is None


def test_cached_only_load_never_writes():
    """缺缓存时只返回 None —— 不解析 PDF、不写盘。

    为什么挑 (2024, 12, 1):它的精确同名 PDF 真的存在,所以万一有人把
    Section A 接回了会写盘的 load_set,这里必然多出一份 JSON —— 这条才真的能红。
    CACHE_DIR 只认 paper_parser 的那一个(两个 loader 都读它),
    指到 tmp 之后,任何误接线写下的文件也只会落在 tmp,污染不到真 parsed_papers/。

    ★ 必须是**顶层** paper_parser:structured.py 用的是
    `from paper_parser import paper`(先插 retrieval/ 进 sys.path),
    retrieval.paper_parser 是**另一个模块对象**,patch 它对这个 loader 无效。
    """
    import tempfile
    import paper_parser

    with tempfile.TemporaryDirectory(prefix="cached_only_test_") as tmp:
        old = paper_parser.CACHE_DIR
        paper_parser.CACHE_DIR = tmp
        try:
            assert load_set_cached_only(2024, 12, 1) is None
            assert os.listdir(tmp) == []
        finally:
            paper_parser.CACHE_DIR = old


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n全部通过 ✅({len(fns)} 个)")
