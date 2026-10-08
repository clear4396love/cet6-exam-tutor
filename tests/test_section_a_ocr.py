import json
import sys
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "reading"))

from sectionA_load import Cloze_Passage
import paddle_ocr


PLAIN_BANK = """A) alpha B) bravo C) charlie D) delta E) echo
F) foxtrot G) golf H) hotel I) india J) juliet
K) kilo L) lima M) mike N) november O) oscar"""

HTML_BANK = """<table><tr><td>A. alpha</td><td>I. india</td></tr>
<tr><td>B. bravo</td><td>J. juliet</td></tr>
<tr><td>C. charlie</td><td>K. kilo</td></tr>
<tr><td>D. delta</td><td>L. lima</td></tr>
<tr><td>E. echo</td><td>M. mike</td></tr>
<tr><td>F. foxtrot</td><td>N. november</td></tr>
<tr><td>G. golf</td><td>O. oscar</td></tr>
<tr><td>H. hotel</td><td></td></tr></table>"""

PASSAGE = " ".join(
    f"word $ \\underline{{{number}}} $" for number in range(26, 36)
)

KEYS = {
    26: "A", 27: "B", 28: "C", 29: "D", 30: "E",
    31: "F", 32: "G", 33: "H", 34: "I", 35: "J",
}


def test_pdf_load_reuses_paddle_markdown_cache(tmp_path, monkeypatch):
    pdf = tmp_path / "CET6_2025年12月_第2套_真题.pdf"
    pdf.write_bytes(b"not a real pdf")
    ocr_dir = tmp_path / "ocr_pdfs"
    cache = ocr_dir / "CET6_2025年12月_第2套_真题_paddle"
    cache.mkdir(parents=True)
    (cache / "meta.json").write_text(
        json.dumps({"pages": 1, "model": "PaddleOCR-VL-1.6"}),
        encoding="utf-8",
    )
    (cache / "doc_000.md").write_text("## Section A\n缓存正文", encoding="utf-8")
    monkeypatch.setattr(paddle_ocr, "OCR_DIR", str(ocr_dir))

    loaded = Cloze_Passage().pdf_load(str(pdf))

    assert [page.page_content for page in loaded] == ["Section A\n缓存正文"]


def test_parse_passage_accepts_paddle_latex_blanks():
    result = Cloze_Passage().parse_passage(f"{PASSAGE}\n{PLAIN_BANK}", KEYS)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    assert len(result["questions"]) == 10
    assert result["questions"]["26"] == {"answer": "A", "answer_word": "alpha"}
    assert result["practice_text"] == " ".join(
        f"word {{{{{number}}}}}" for number in range(26, 36)
    )
    assert result["text"] == " ".join("word" for _ in range(26, 36))


def test_parse_passage_accepts_spaces_before_word_bank_punctuation():
    spaced_bank = PLAIN_BANK.replace(")", " )")

    result = Cloze_Passage().parse_passage(f"{PASSAGE}\n{spaced_bank}", KEYS)

    assert result is not None
    assert len(result["words"]) == 15
    assert result["words"]["A"] == "alpha"
    assert result["words"]["O"] == "oscar"


def test_extract_accepts_zhipu_plain_numbered_blanks():
    passage = "In 2026, the study found people 26 accurate. It measured how they act 27 moment to moment. " \
              "Recorders 28 audio, participants 29 their behavior, and the study lasted 30 weeks. " \
              "Observers rated 31 of themselves; this 32 may reflect clips, not 33 language. " \
              "There are 34 explanations, and people may 35 rude behavior."
    pages = _pages(
        f"Part III\nReading Comprehension\nSection A\nQuestions 26 to 35 are based on the following passage.\n"
        f"{passage}\n{HTML_BANK}\nSection B\n",
        _keys_page("ABCDEFGHIJ"),
    )

    result = Cloze_Passage().extract(pages)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    assert len(result["questions"]) == 10
    assert _answers(result) == "ABCDEFGHIJ"
    assert "2026" in result["text"]
    assert "Questions 26 to 35" not in result["text"]
    assert [result["practice_text"].find(f"{{{{{number}}}}}") for number in range(26, 36)] == sorted(
        result["practice_text"].find(f"{{{{{number}}}}}") for number in range(26, 36)
    )
    assert all(result["practice_text"].count(f"{{{{{number}}}}}") == 1 for number in range(26, 36))
    assert "2026" in result["practice_text"]


def test_parse_passage_ignores_unrelated_numbers_between_numbered_blanks():
    passage = (
        "The study found 26 facts, and reported 27 results. It compared 28 groups, "
        "then listed 29 changes. The author entered the market at 31. "
        "It was quite a 30, given the earlier results. She did not celebrate her "
        "30th birthday as she had 31. Later, the report described 32 causes, "
        "33 effects, 34 examples, and 35 outcomes."
    )

    result = Cloze_Passage().parse_passage(f"{passage}\n{HTML_BANK}", KEYS)

    assert result is not None
    assert set(result["questions"]) == {str(number) for number in range(26, 36)}
    assert "at 31" in result["text"]
    assert "30th birthday" in result["text"]
    assert "quite a ," in result["text"]


def test_parse_passage_does_not_treat_unrelated_numbers_as_blank_marks():
    result = Cloze_Passage().parse_passage(
        f"In 2026, 26 people were surveyed.\n{HTML_BANK}", KEYS
    )

    assert result is None


def test_parse_passage_accepts_html_dot_word_bank():
    result = Cloze_Passage().parse_passage(f"{PASSAGE}\n{HTML_BANK}", KEYS)

    assert result is not None
    assert result["words"] == {
        "A": "alpha", "B": "bravo", "C": "charlie", "D": "delta",
        "E": "echo", "F": "foxtrot", "G": "golf", "H": "hotel",
        "I": "india", "J": "juliet", "K": "kilo", "L": "lima",
        "M": "mike", "N": "november", "O": "oscar",
    }
    assert "<table" not in result["text"]


def test_parse_keys_accepts_section_a_html_answer_table():
    page = SimpleNamespace(
        page_content="""## KEYS
<table><tr><td>26</td><td>27</td><td>28</td><td>29</td><td>30</td><td>31</td><td>32</td><td>33</td><td>34</td><td>35</td></tr>
<tr><td>B</td><td>H</td><td>A</td><td>L</td><td>J</td><td>M</td><td>C</td><td>E</td><td>D</td><td>O</td></tr></table>
"""
    )

    answers = Cloze_Passage().parse_keys([page])

    assert {number: answers[number] for number in range(26, 36)} == {
        26: "B", 27: "H", 28: "A", 29: "L", 30: "J",
        31: "M", 32: "C", 33: "E", 34: "D", 35: "O",
    }


# ---- 整卷形状:按 Phase 8 判定的两个结构缺陷做最小复现 ----
# 每个 fixture 只用该卷真实的 KEYS 串当答案,断言到答案串级别,
# 这样"题号-字母-单词"错位不会伪装成解析成功。

def _pages(*texts):
    return [SimpleNamespace(page_content=text) for text in texts]


def _blank(number):
    return f"$ \\underline{{{number}}} $"


def _keys_page(letters):
    numbers = "".join(f"<td>{number}</td>" for number in range(26, 36))
    cells = "".join(f"<td>{letter}</td>" for letter in letters)
    return f"KEYS\n<table><tr>{numbers}</tr>\n<tr>{cells}</tr></table>"


def _answers(result):
    return "".join(result["questions"][str(n)]["answer"] or "?" for n in range(26, 36))


_PASSAGE_TEMPLATE = (
    "American colleges and universities are using less coal than they did a decade ago, "
    "the U.S. Energy Information Administration said in a report {} yesterday. "
    "All 57 schools that were burning coal in 2008 are using less now, and 20 have {} coal completely. "
    "Most universities have turned to natural gas as a {}, with state funding backing the fuel switch. "
    "Campus coal use has a history dating back to the 1800s when {} to power was scarce. "
    "Some schools made an 80 percent cut, and others have {} their use sharply. "
    "Officials say the {} of the fuel switch is largely financial. "
    "Colleges also face pressure to {} emissions on campus. "
    "A few have {} the move to renewables entirely. "
    "Analysts expect the {} to continue as prices fall. "
    "The report calls the trend a {} of what is possible."
)
BLANKS_PASSAGE = _PASSAGE_TEMPLATE.format(*[_blank(n) for n in range(26, 36)])

PLAIN_BANK_15 = """A. abandoned
B. access
C. consumption
D. contrive
E. duplications
F. investments
G. mobilized
H. negligent
I. neutral
J. reductions
K. released
L. replacement
M. slash
N. surplus
O. void"""

# 2023_6_3 与 2020_12_2 的真实 OCR 词库:双栏排版,右栏的 I 行被读成 B,
# 于是同一个 B 下挤了两个词、I 整个消失。
DUP_LETTER_BANK = """A. activated

B. probes

B. articulates

J. random

C. assessment K. recall

D. consecutive

L. relatively

E. cues M. saturated

F. deny N. symptoms

G. discrepancy O. terminate

H. probably"""

DIRECTIONS = (
    "Directions: In this section, there is a passage with ten blanks. You are required to "
    "select one word for each blank from a list of choices given in a word bank following "
    "the passage. You may not use any of the words in the bank more than once."
)
LISTENING = (
    "Part II\nListening Comprehension\n\nSection A\nDirections: In this section, you will hear "
    "three news reports.\nSection B\nDirections: In this section, you will hear two long "
    "conversations.\nSection C\nDirections: In this section, you will hear three recordings."
)


def test_extract_uses_blank_marks_when_reading_heading_missing():
    """2021_12_2 形状:阅读横幅字面只在卷尾答案页出现,正文页没有标题文字。"""
    pages = _pages(
        LISTENING,
        f"Section A\n{DIRECTIONS}\n\n{BLANKS_PASSAGE}\n{PLAIN_BANK_15}\nSection B\nDirections: ...",
        f"{_keys_page('BDOAIEGJMF')}\nPart IV Translation\nPart III Reading Comprehension",
    )

    result = Cloze_Passage().extract(pages)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    assert len(result["words"]) == 15
    assert _answers(result) == "BDOAIEGJMF"
    assert result["questions"]["26"] == {"answer": "B", "answer_word": "access"}


def test_extract_falls_back_when_directions_sentence_absent():
    """2022_12_3 形状:标题和块都正常,但整卷没有 Directions 原句。"""
    pages = _pages(
        f"Part III\nReading Comprehension\n(40 minutes)\nSection A\n\n"
        f"{BLANKS_PASSAGE}\n{PLAIN_BANK_15}\nSection B\nDirections: ...",
        _keys_page("KALBNMIFJC"),
    )

    result = Cloze_Passage().extract(pages)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    assert len(result["words"]) == 15
    assert _answers(result) == "KALBNMIFJC"


def test_extract_returns_blank_range_without_directions_and_duplicate_bank_letter():
    """2023_6_3 形状:同上去掉 Directions,且词库缺 I(右栏 I 行被 OCR 读成 B)。"""
    pages = _pages(
        f"Part III\nReading Comprehension\n(40 minutes)\nSection A\n\n"
        f"{BLANKS_PASSAGE}\n{DUP_LETTER_BANK}\nSection B\nDirections: ...",
        _keys_page("LIAKDCGEHF"),
    )

    result = Cloze_Passage().extract(pages)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    # 缺 I 是 OCR 误识,不属本轮修复范围:词库就是 14 个,本题 answer_word 为 None。
    assert len(result["words"]) == 14
    assert "I" not in result["words"]
    assert _answers(result) == "LIAKDCGEHF"
    assert result["questions"]["27"] == {"answer": "I", "answer_word": None}


def test_extract_stays_none_without_reading_banner():
    """2021_6_1 形状:整卷连阅读横幅字面都没有 → 本轮不启用兜底,仍返回 None。"""
    pages = _pages(
        LISTENING,
        f"Section A\n{BLANKS_PASSAGE}\n{PLAIN_BANK_15}\nSection B\nDirections: ...",
    )

    assert Cloze_Passage().extract(pages) is None


def test_extract_keeps_directions_path_for_2022_6_1_shape():
    """对照卷 2022_6_1 形状:标题 + Directions 都在 → 老路径输出不变。"""
    pages = _pages(
        f"Part III\nReading Comprehension\n(40 minutes)\nSection A\n{DIRECTIONS}\n\n"
        f"{BLANKS_PASSAGE}\n{PLAIN_BANK_15}\nSection B\nDirections: ...",
        _keys_page("ABKHJGLIEF"),
    )

    result = Cloze_Passage().extract(pages)

    assert result is not None
    assert (result["q_from"], result["q_to"]) == (26, 35)
    assert len(result["words"]) == 15
    assert _answers(result) == "ABKHJGLIEF"


def test_extract_skips_section_a_without_all_ten_answers():
    section_a = (
        f"Part III\nReading Comprehension\nSection A\n{DIRECTIONS}\n"
        f"{BLANKS_PASSAGE}\n{PLAIN_BANK_15}\nSection B\n"
    )

    for key_page in ("", _keys_page("ABCDEFGHI")):
        assert Cloze_Passage().extract(_pages(section_a, key_page)) is None
