"""从用户原话中确定性提取年份、月份、套数、板块和题号。"""
import re

# 中文数字 → 阿拉伯数字。
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# 用户说的板块词 → metadata 里的 section 值。
_SECTION_WORDS = {
    "写作": "writing", "作文": "writing", "writing": "writing",
    "听力": "listening", "listening": "listening",
    "阅读": "reading", "reading": "reading",
    "翻译": "translation", "translation": "translation",
    "答案": "keys", "keys": "keys",
}


def _to_int(s: str) -> int:
    """把中文/阿拉伯数字字符串都转成 int。'十六' → 16，'42' → 42。"""
    if s.isdigit():
        return int(s)
    if "十" in s:
        tens, ones = s.split("十", 1)
        return _CN_NUM.get(tens, 1) * 10 + _CN_NUM.get(ones, 0)
    return _CN_NUM[s]


def _strict_int(value) -> int | None:
    """只接受真正的整数值：允许 42.0，拒绝 42.9 和 bool。"""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else None


def parse_conditions(query: str) -> dict:
    """从问题里抽 year / month / exam_set / section / question_number。
    收:用户输入的问题,吐出字典,里面包含年月,套数,题号等
    抽不到就直接返回原输入。question_number 抽得到但过滤不了（库里没存题号），
    留给上层（意图识别）判断用。

    >>> parse_conditions("2024年12月第1套翻译讲了什么")
    {'year': 2024, 'month': 12, 'exam_set': 1, 'section': 'translation'}
    >>> parse_conditions("第一套第42题为什么选A")
    {'question_number': 42, 'exam_set': 1}
    >>> parse_conditions("第一题选什么")
    {'question_number': 1}
    >>> parse_conditions("随便问问")
    {}
    """
    cond = {}
    m = re.search(r"20\d{2}", query)           # 年份：2024
    if m:
        cond["year"] = int(m.group(0))
    m = re.search(
        r"(?<!\d)([一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九]|\d{1,2})(?!\d)\s*月",
        query,
    )
    if m:
        cond["month"] = _to_int(m.group(1))

    # 题号："第42题"/"42题"/"第一题"（第可有可无；先抽题号，"第一"才不会跟套数混淆）
    # ★ 相对题号短语（"下一题"/"上一题"/"前一题"/"后一题"）不是数字题号：
    #   先从题号匹配文本里剔除，否则其中的"一题"会被读成第 1 题。
    #   只影响题号；年/月/套/板块仍从原始 query 提取（同句年月套要保留）。
    question_query = re.sub(r"[上下前后]\s*一\s*题", "", query)
    m = re.search(
        r"(?<!\d)(?:第\s*)?([一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九]|\d{1,3})(?!\d)\s*题",
        question_query,
    )
    if m:
        cond["question_number"] = _to_int(m.group(1))

    # 套数："第一套"/"第一份"/"第1套"（"第一题"里没有套/份，不会误配）
    m = re.search(r"第\s*([一二三四五六七八九]|\d)\s*(套|份)", query)
    if m:
        cond["exam_set"] = _to_int(m.group(1))

    for word, sec in _SECTION_WORDS.items():   # 板块：翻译/听力/阅读…
        if word in query:
            cond["section"] = sec
            break
    return cond


def sanitize_position(raw: dict) -> dict:
    """收:LLM 输出的定位字段(可能不干净);吐:只含合法字段的 dict。
    把 month=13、year=24、section="翻译" 这类值清洗成合法值。
    非法字段逐字段丢弃(不整段崩)——定位字段是"质量增益",丢了靠向量检索兜底。

    >>> sanitize_position({"year": "2024", "month": 13, "exam_set": 1.0,
    ...                    "section": "翻译", "question_number": "44", "option": "B"})
    {'year': 2024, 'exam_set': 1, 'section': 'translation', 'question_number': 44}
    >>> sanitize_position({"year": 24, "month": None, "section": "不认识的板块"})
    {}
    >>> sanitize_position(None)
    {}
    """
    clean = {}
    if not isinstance(raw, dict):
        return {}
    # 年份:要 4 位数、2000-2029。字符串/浮点都转 int("2024"→2024, 2024.0→2024)。
    if raw.get("year") is not None:
        y = _strict_int(raw["year"])
        if y is not None and 2000 <= y <= 2029:
            clean["year"] = y
    # 月份:1-12
    if raw.get("month") is not None:
        m = _strict_int(raw["month"])
        if m is not None and 1 <= m <= 12:
            clean["month"] = m
    # 套数:1-3
    if raw.get("exam_set") is not None:
        e = _strict_int(raw["exam_set"])
        if e is not None and 1 <= e <= 3:
            clean["exam_set"] = e
    # 板块:中文/英文都归一(_SECTION_WORDS 的值),落点必须在集合内
    if raw.get("section"):
        sec = str(raw["section"]).strip().lower()
        if sec in _SECTION_WORDS:
            clean["section"] = _SECTION_WORDS[sec]
    # 题号:1-100
    if raw.get("question_number") is not None:
        q = _strict_int(raw["question_number"])
        if q is not None and 1 <= q <= 100:
            clean["question_number"] = q
    return clean


# ---------- 相对指代:无法安全换算的表达 ----------
#
# 为什么不换算:"去年"分不清是相对现实年份还是相对当前讨论年份;而"上一套/下一题"
# 的基准既可能是定位表、也可能是同句里的数字。第一版决定一律不猜 → 拦下来让用户说清。
_RELATIVE_MOVES = (
    "上一套", "下一套",
    "上一题", "下一题", "前一题", "后一题",
)
_RELATIVE_YEARS = ("今年", "去年", "前年")


def unsafe_relative_references(text: str, position: dict) -> tuple[str, ...]:
    """返回本轮所有无法安全换算的相对表达；全部安全时返回 ()。

    只做判断:不读时钟、不读会话表、不修改 position。
    - 套数/题号移动词:出现即拦(同句的数字只可能是移动基准,不是最终查询目标)。
    - 年份相对词:position 里已有合法 year 时才放行("2025年今年…"以 2025 为准)。
    - 每个词最多返回一次;顺序固定:先移动词,后年份词。
    """
    found: list[str] = []
    for word in _RELATIVE_MOVES:
        if word in text:
            found.append(word)
    if not position.get("year"):
        for word in _RELATIVE_YEARS:
            if word in text:
                found.append(word)
    return tuple(found)


if __name__ == "__main__":
    # 快速自测（不用装任何东西）
    cases = [
        
        "随便问问",
    ]
    for q in cases:
        cond = parse_conditions(q)
        print(f"问题：{q!r}\n  抽到：{cond}\n")
