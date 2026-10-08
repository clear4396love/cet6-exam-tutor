# -*- coding: utf-8 -*-
"""题目级结构化数据访问层。

只读 flat JSON 缓存 + 纯函数,不连 LLM、不碰库。给 service.py 的结构化主分支用。

答案字母一律来自缓存(KEYS 解析或用户注入),本层绝不猜、绝不改判。
"""
import os
import re
import sys

# ★ 与 generation.py 同款:先插 retrieval/ 进 sys.path,再顶层 import paper_parser
# (service.py 用包式 retrieval.xxx 导入,缓存脚本用顶层导入,两种都要兼容)
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)
from paper_parser import paper

# 题号区间 → 题型(默认路由;解析器用实际版式验证,见改造计划)
_QTYPE_RANGES = [
    (range(26, 36), "fill_blank"),
    (range(36, 46), "paragraph_matching"),
    (range(46, 56), "multiple_choice"),
]

# 全角标点 → 半角(OCR/文字层常带中文标点)
_FULLWIDTH = str.maketrans({
    "）": ")", "（": "(", "，": ",", "。": ".", "．": ".",
    "：": ":", "；": ";", "？": "?", "！": "!", "“": '"',
    "”": '"', "‘": "'", "’": "'",
})

_MAX_PARAGRAPH_CHARS = 500   # 段落贴进证据的最大长度(控 token)

_EXPLAIN_HINTS = ("为什么", "为啥", "为什么不", "为什么选", "为什么不选", "解析", "解释",
                  "怎么选", "怎么来的", "对在哪", "错在哪", "哪里不对", "哪里错")


# ---------- flat JSON 访问器 ----------

def get_questions(paper: dict) -> dict:
    return paper.get("questions", {})


def get_paragraphs(paper: dict) -> dict:
    return paper.get("paragraphs", {})


def get_question(paper: dict, qnum: int) -> dict | None:
    q = get_questions(paper).get(str(qnum))
    return q if isinstance(q, dict) else None


def get_answer(paper: dict, qnum: int) -> str | None:
    q = get_question(paper, qnum)
    if q is None:
        return None
    ans = q.get("answer")
    return ans if isinstance(ans, str) and ans else None


# ---------- 功能函数 ----------

def qtype_of(qnum: int) -> str | None:
    for rng, name in _QTYPE_RANGES:
        if qnum in rng:
            return name
    return None


def clean_text(s: str) -> str:
    """轻清洗:去首尾杂字符、压缩空白、全角标点转半角。

    不做词间补空格——OCR 批次的词粘连(Employersattachmoreimportance...)不可逆,
    硬拆风险高;脏句照贴,靠模型从上下文理解(见扫描SOP 边界)。
    """
    if not s:
        return ""
    s = s.strip()
    s = s.lstrip("()[]（）　")          # 去掉段首杂字符,如 ")If contributing..."
    # 去掉行尾的页眉残留,如 "六级2021年6月48"
    s = re.sub(r"\s*六级\d{4}年\d{1,2}月\d+\s*$", "", s)
    s = s.translate(_FULLWIDTH)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_mention_letter(text: str) -> str | None:
    """从问句里抓用户提到的字母(A~R)。只提取,不解释含义。

    字母代表"段落"(段落匹配)还是"选项"(仔细阅读)由调用方按题型决定——
    本函数不知道题型。宁可漏抓不可错抓:普通英文单词里的 A/B 不当字母。
    """
    if not text:
        return None
    # 1) 紧跟"选/为什么不选/为什么选"的字母最可靠:"为什么不选 D" "为什么选K"
    m = re.search(r"(?:为什么\s*不?\s*选|选)\s*([A-R])(?![A-Za-z])", text)
    if m:
        return m.group(1)
    # 2) 用户直接点名段落问错因:"A段错在哪里" "B段哪里不对"。
    m = re.search(r"(?<![A-Za-z])([A-R])\s*段(?:落)?[^。？！]*(?:错|不对)", text)
    if m:
        return m.group(1)
    # 3) 兜底:带"呢/那"的追问里抓独立字母:"那B呢"(此时不触发模式1)
    if re.search(r"呢|那|选", text):
        m = re.search(r"(?<![A-Za-z])([A-R])(?![A-Za-z])", text)
        if m:
            return m.group(1)
    return None


def wants_explanation(text: str) -> bool:
    """判断问句是要"为什么/怎么选"的长讲解,还是只要答案字母。"""
    return any(h in text for h in _EXPLAIN_HINTS)


def load_set(year: int, month: int, exam_set: int) -> dict | None:
    """按 (year, month, exam_set) 读一套缓存;无缓存且文字层会自动重建写盘,扫描/缺 PDF 返回 None。"""
    return paper().json_load(year, month, exam_set)


def load_set_cached_only(year: int, month: int, exam_set: int) -> dict | None:
    """只读缓存版 load_set:不解析 PDF、不写盘。

    和 load_set 只差这一点 —— Section A/C 不参与「缺缓存就重建」:
    没有现成 JSON 就按缺数据降级。
    (留着这层壳是为了让测试能按名字 patch。)
    """
    data = paper().json_load_cached(year, month, exam_set)
    return data if isinstance(data, dict) else None


def get_section_a_answer(paper: dict, qnum: int) -> tuple[str, str] | None:
    """Section A 第 qnum 空的 (答案字母, 单词)。

    数据缺、结构损坏、答案字母不在词库里、或 answer_word 和词库对不上 → 一律 None。
    对不上说明这份缓存不可信,宁可回「查不到」也不猜。
    """
    if not isinstance(paper, dict):
        return None
    sa = paper.get("section_a")
    if not isinstance(sa, dict):
        return None
    questions, words = sa.get("questions"), sa.get("words")
    if not (isinstance(questions, dict) and isinstance(words, dict)):
        return None
    q = questions.get(str(qnum))          # JSON 键是字符串
    if not isinstance(q, dict):
        return None
    letter, word = q.get("answer"), q.get("answer_word")
    if not (isinstance(letter, str) and letter and isinstance(word, str) and word):
        return None
    if words.get(letter) != word:
        return None
    return letter, word


def get_section_c_question(paper: dict, qnum: int) -> tuple[str, str] | None:
    """从仔细阅读缓存中取得题目的答案字母和对应选项。"""
    section = paper.get("section_c") if isinstance(paper, dict) else None
    passages = section.get("passages") if isinstance(section, dict) else None
    if not isinstance(passages, list):
        return None
    for passage in passages:
        questions = passage.get("questions") if isinstance(passage, dict) else None
        question = questions.get(str(qnum)) if isinstance(questions, dict) else None
        if not isinstance(question, dict):
            continue
        letter, options = question.get("answer"), question.get("options")
        if letter not in ("A", "B", "C", "D") or not isinstance(options, dict):
            return None
        option = options.get(letter)
        return (letter, option.strip()) if isinstance(option, str) and option.strip() else None
    return None


def build_section_c_evidence(paper: dict, qnum: int) -> str | None:
    """把本题所属文章、题干、四个选项和缓存答案交给讲解模型。"""
    pair = get_section_c_question(paper, qnum)
    if pair is None:
        return None
    passages = paper["section_c"]["passages"]
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        questions = passage.get("questions")
        question = questions.get(str(qnum)) if isinstance(questions, dict) else None
        if not isinstance(question, dict):
            continue
        text, stem, options = passage.get("text"), question.get("stem"), question.get("options")
        if not (isinstance(text, str) and text.strip()
                and isinstance(stem, str) and stem.strip()
                and isinstance(options, dict)
                and all(isinstance(options.get(letter), str) and options[letter].strip()
                        for letter in "ABCD")):
            return None
        lines = [f"[题目]第{qnum}题(仔细阅读)", f"[原文]{text.strip()}", f"[题干]{stem.strip()}"]
        lines.extend(f"[选项{letter}]{options[letter].strip()}" for letter in "ABCD")
        lines.append(f"[答案(KEYS)]{pair[0]}")
        return "\n\n".join(lines)
    return None


def _para_for(paragraphs: dict, letter: str) -> str | None:
    if not letter or letter not in paragraphs:
        return None
    return clean_text(paragraphs[letter][:_MAX_PARAGRAPH_CHARS])


def build_evidence(parsed: dict, qnum: int, mention_letter: str | None = None) -> str:
    """拼段落匹配的带类型证据(只给"为什么"讲解用)。

    [题干] / [用户问的段落X](若有且≠答案段) / [答案(KEYS)] / [原文段落{答案}] / [相邻段落]
    答案从缓存取,不猜。答案段缺了仍给出可读证据但明示,不造假。
    """
    q = get_question(parsed, qnum)
    stem = clean_text(q["stem"]) if q else ""
    ans = get_answer(parsed, qnum)
    paragraphs = get_paragraphs(parsed)

    parts = [f"[题目]第{qnum}题(段落匹配)"]
    if stem:
        parts.append(f"[题干]{stem}")

    # 用户提到的段落(≠答案段才单独贴,免得与答案段重复)
    mention = mention_letter if mention_letter and mention_letter != ans else None
    pm = _para_for(paragraphs, mention)
    if pm:
        parts.append(f"[用户问的段落{mention}]{pm}")

    parts.append(f"[答案(KEYS)]{ans}" if ans else "[答案(KEYS)]无")

    am = _para_for(paragraphs, ans)
    if am:
        parts.append(f"[原文段落{ans}]{am}")
    elif ans:
        parts.append(f"[原文段落{ans}]该段落不在缓存中(数据缺)")

    # 相邻段(答案段前一/后一段),控 token
    ordered = [k for k in sorted(paragraphs)]
    if ans and ans in paragraphs:
        idx = ordered.index(ans)
        for neighbor in (ordered[idx - 1] if idx > 0 else None,
                         ordered[idx + 1] if idx < len(ordered) - 1 else None):
            nm = _para_for(paragraphs, neighbor)
            if nm:
                parts.append(f"[相邻段落{neighbor}]{nm}")

    return "\n\n".join(parts)
