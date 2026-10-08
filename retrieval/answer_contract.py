"""Deterministic shape and KEYS checks for generated reading explanations."""

import re

from retrieval.answer_prompt import SECTION_B_HEADINGS, SECTION_C_HEADINGS


_ANSWER_CLAIM = re.compile(
    r"(?:标准答案|正确答案|正确选项|正确的是|答案|应选|应该选|所以选|因此选|最终选|故选|"
    r"所以(?:应该|应当|应)?选|第\s*\d+\s*题\s*(?:应该|应当|应|该)?选)"
    r"\s*(?:其实|应该|应当|应|就)?\s*(?:是|为|：|:)?\s*([A-R])(?![A-Za-z])",
    re.IGNORECASE,
)
_REVERSE_ANSWER_CLAIM = re.compile(
    r"(?<![A-Za-z])([A-R])\s*(?:才|就|应该|应当|应)?\s*是\s*(?:标准答案|正确答案|正确选项)",
    re.IGNORECASE,
)


def conflicting_answer_claim(text: str, answer: str) -> bool:
    """Flag recognized explicit answer claims that disagree with KEYS."""
    if not isinstance(text, str) or not isinstance(answer, str):
        return True
    claims = [match.group(1).upper() for pattern in (_ANSWER_CLAIM, _REVERSE_ANSWER_CLAIM)
              for match in pattern.finditer(text)]
    return any(letter != answer.strip().upper() for letter in claims)


def valid_explanation(text: str, section: str, answer: str) -> bool:
    """Accept only the requested eight headings and no explicit conflicting answer."""
    if section not in {"B", "C"} or not isinstance(text, str) or not isinstance(answer, str):
        return False
    answer = answer.strip().upper()
    allowed = "ABCD" if section == "C" else "ABCDEFGHIJKLMNOPQR"
    if answer not in allowed:
        return False
    template = SECTION_B_HEADINGS if section == "B" else SECTION_C_HEADINGS
    expected = [name.replace("[答案]", answer) for name in template]
    headings = []
    bodies = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("**") and line.endswith("**"):
            name = line[2:-2].strip()
            headings.append(name)
            bodies.append([])
            continue
        if line and bodies:
            bodies[-1].append(line)
    return headings == expected and all(bodies) and not conflicting_answer_claim(text, answer)
