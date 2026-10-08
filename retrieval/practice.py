"""Small, deterministic helpers for one-at-a-time reading practice."""

import re
from collections import Counter
from collections.abc import Mapping, Sequence

from retrieval.structured import (
    clean_text, get_answer, get_paragraphs, get_question,
    get_section_a_answer, get_section_c_question,
)


_LETTERS = set("ABCDEFGHIJKLMNOPQR")
_CLOZE_LETTERS = set("ABCDEFGHIJKLMNO")
_CHOICE_LETTERS = set("ABCD")
_MARKER = re.compile(r"\{\{(\d+)\}\}")


def _cloze_item(paper: dict, question_number: int) -> dict | None:
    section = paper.get("section_a")
    if not isinstance(section, dict):
        return None
    practice, body, words = section.get("practice_text"), section.get("text"), section.get("words")
    if not isinstance(practice, str) or not isinstance(body, str) or not isinstance(words, dict):
        return None
    if _MARKER.findall(practice) != [str(n) for n in range(26, 36)]:
        return None
    if re.sub(r"\s+([,.!?;:])", r"\1", clean_text(_MARKER.sub("", practice))) != re.sub(
        r"\s+([,.!?;:])", r"\1", clean_text(body)
    ):
        return None
    if set(words) != _CLOZE_LETTERS or any(not isinstance(word, str) or not word.strip() for word in words.values()):
        return None
    if any(get_section_a_answer(paper, n) is None for n in range(26, 36)):
        return None
    return {"question_number": question_number, "practice_text": practice, "words": words.copy()}


def _section_c_item(paper: dict, question_number: int) -> dict | None:
    section = paper.get("section_c")
    passages = section.get("passages") if isinstance(section, dict) else None
    if not isinstance(passages, list):
        return None
    matches = []
    for passage in passages:
        questions = passage.get("questions") if isinstance(passage, dict) else None
        if isinstance(questions, dict) and str(question_number) in questions:
            matches.append((passage, questions[str(question_number)]))
    if len(matches) != 1:
        return None
    passage, question = matches[0]
    if not isinstance(question, dict):
        return None
    text, stem, options = passage.get("text"), question.get("stem"), question.get("options")
    if (not isinstance(text, str) or not isinstance(stem, str)
            or not isinstance(options, dict) or set(options) != _CHOICE_LETTERS
            or question.get("answer") not in _CHOICE_LETTERS
            or any(not isinstance(value, str) or not clean_text(value) for value in options.values())):
        return None
    text, stem = clean_text(text), clean_text(stem)
    if not text or not stem or get_section_c_question(paper, question_number) is None:
        return None
    return {"question_number": question_number, "passage_text": text,
            "stem": stem, "options": {letter: clean_text(options[letter]) for letter in "ABCD"}}


def get_practice_item(paper: dict, question_number: int) -> dict | None:
    """Return a new answer-free view only when the question can be graded."""
    if isinstance(paper, dict) and type(question_number) is int and 26 <= question_number <= 35:
        return _cloze_item(paper, question_number)
    if isinstance(paper, dict) and type(question_number) is int and 46 <= question_number <= 55:
        return _section_c_item(paper, question_number)
    if (not isinstance(question_number, int) or not 36 <= question_number <= 45
            or not isinstance(paper, dict) or not isinstance(paper.get("questions"), dict)
            or not isinstance(paper.get("paragraphs"), dict)):
        return None
    question = get_question(paper, question_number)
    paragraphs = get_paragraphs(paper)
    answer = get_answer(paper, question_number)
    if not question or not isinstance(paragraphs, dict) or not isinstance(answer, str):
        return None
    answer = answer.strip().upper()
    raw_stem = question.get("stem")
    if not isinstance(raw_stem, str):
        return None
    stem = clean_text(raw_stem)
    visible = {
        letter: clean_text(value)
        for letter, value in paragraphs.items()
        if letter in _LETTERS and isinstance(value, str) and clean_text(value)
    }
    if not stem or answer not in visible:
        return None
    return {"question_number": question_number, "stem": stem, "paragraphs": visible}


def grade_attempt(paper: dict, question_number: int, submitted_answer: str) -> dict | None:
    """Compare one normalized A–R letter with the cached KEYS answer."""
    if not isinstance(submitted_answer, str) or get_practice_item(paper, question_number) is None:
        return None
    submitted = submitted_answer.strip().upper()
    if 26 <= question_number <= 35:
        if submitted not in _CLOZE_LETTERS:
            return None
        answer, word = get_section_a_answer(paper, question_number)
        return {"submitted": submitted, "answer": answer, "correct": submitted == answer,
                "answer_word": word}
    if 46 <= question_number <= 55:
        if submitted not in _CHOICE_LETTERS:
            return None
        answer, _ = get_section_c_question(paper, question_number)
        return {"submitted": submitted, "answer": answer, "correct": submitted == answer}
    if submitted not in _LETTERS:
        return None
    answer = get_answer(paper, question_number).strip().upper()
    return {"submitted": submitted, "answer": answer, "correct": submitted == answer}


def summarize_attempts(events: Sequence[Mapping[str, object]]) -> dict:
    """Summarize only completed answer submissions from the supplied session."""
    attempts = [
        row for row in events
        if isinstance(row, Mapping)
        and row.get("stage") in {"attempt_correct", "attempt_wrong"}
        and isinstance(row.get("attempt_correct"), bool)
        and isinstance(row.get("attempt_answer"), str)
    ]
    count = len(attempts)
    correct = sum(row["attempt_correct"] for row in attempts)
    recent = attempts[-5:]
    by_range = {
        "26-35": {"attempts": 0, "correct": 0},
        "36-40": {"attempts": 0, "correct": 0},
        "41-45": {"attempts": 0, "correct": 0},
        "46-50": {"attempts": 0, "correct": 0},
        "51-55": {"attempts": 0, "correct": 0},
    }
    misses = Counter()
    for row in attempts:
        filters = row.get("filters")
        if not isinstance(filters, Mapping):
            continue
        qnum = filters.get("question_number")
        if not isinstance(qnum, int):
            continue
        group = ("26-35" if 26 <= qnum <= 35 else "36-40" if 36 <= qnum <= 40
                 else "41-45" if 41 <= qnum <= 45 else "46-50" if 46 <= qnum <= 50
                 else "51-55" if 51 <= qnum <= 55 else None)
        if group:
            by_range[group]["attempts"] += 1
            by_range[group]["correct"] += row["attempt_correct"]
            if not row["attempt_correct"]:
                paper_key = (filters.get("year"), filters.get("month"), filters.get("exam_set"), qnum)
                misses[paper_key] += 1
    return {
        "attempt_count": count,
        "correct_count": correct,
        "accuracy": correct / count if count else 0.0,
        "recent_accuracy": sum(row["attempt_correct"] for row in recent) / len(recent) if recent else 0.0,
        "by_range": by_range,
        "repeated_misses": sorted({key[-1] for key, missed in misses.items() if missed >= 2}),
        "tier": "plan_insufficient_data" if count < 3 else "weakness_snapshot" if count < 8 else "session_review",
    }


def summarize_learning(events: Sequence[Mapping[str, object]],
                       preferred_section: str | None = None) -> dict:
    """Summarize durable events; objective reading facts never come from model feedback."""
    rows = [row for row in events if isinstance(row, Mapping)]
    reading = summarize_attempts(rows)
    drafts = [row for row in rows if row.get("kind") == "draft_submitted"]
    feedback = {row.get("draft_id"): row.get("feedback") for row in rows
                if row.get("kind") == "feedback_ready" and row.get("draft_id")}
    groups = {}
    for row in rows:
        if row.get("kind") != "reading_attempt" or not isinstance(row.get("filters"), Mapping):
            continue
        location = row["filters"]
        key = tuple(location.get(name) for name in ("year", "month", "exam_set", "question_number"))
        if any(type(value) is not int for value in key) or type(row.get("attempt_correct")) is not bool:
            continue
        group = groups.setdefault(key, {"year": key[0], "month": key[1], "exam_set": key[2],
                                        "question_number": key[3], "wrong_count": 0,
                                        "latest_correct": False})
        group["wrong_count"] += not row["attempt_correct"]
        group["latest_correct"] = row["attempt_correct"]

    latest_draft = drafts[-1] if drafts else None
    latest_status = ("ready" if latest_draft and latest_draft.get("draft_id") in feedback
                     else "pending" if latest_draft else "none")
    practice = [row for row in rows if row.get("kind") in {"reading_attempt", "draft_submitted"}
                and (preferred_section is None or row.get("section") == preferred_section)]
    latest = practice[-1] if practice else None
    target = None
    if latest and latest.get("kind") == "draft_submitted":
        draft_id = latest.get("draft_id")
        target = {"draft_id": draft_id}
        label = "作文" if latest.get("section") == "writing" else "翻译"
        if draft_id in feedback:
            priority = feedback[draft_id].get("priority", "复查全文")
            action = f"按 AI 参考评语，先修改这篇{label}：{priority}。"
        else:
            action = f"重试评阅这篇已保存的{label}原稿。"
    elif latest and latest.get("kind") == "reading_attempt" and latest.get("attempt_correct") is False:
        location = latest.get("filters", {})
        key = tuple(location.get(name) for name in ("year", "month", "exam_set", "question_number"))
        group = groups.get(key)
        if group and group["latest_correct"] is False:
            target = dict(location)
            action = (f"复盘{key[0]}年{key[1]}月第{key[2]}套第{key[3]}题，"
                      "先对照原文证据再重做。")
        else:
            action = "选择一道已收录的阅读题，先提交一次答案。"
    elif preferred_section == "writing":
        action = "选择一套已收录的作文题，提交一篇原稿。"
    elif preferred_section == "translation":
        action = "选择一套已收录的翻译题，提交一篇译文。"
    else:
        action = "选择一道已收录的阅读题，先提交一次答案。"
    return {
        "reading": reading, "repetition_groups": list(groups.values()),
        "writing_count": sum(row.get("section") == "writing" for row in drafts),
        "translation_count": sum(row.get("section") == "translation" for row in drafts),
        "writing_revisions": sum(row.get("section") == "writing" and row.get("revision_of") is not None
                                 for row in drafts),
        "translation_revisions": sum(row.get("section") == "translation" and row.get("revision_of") is not None
                                     for row in drafts),
        "latest_feedback_status": latest_status,
        "next_action": action, "next_action_target": target,
    }
