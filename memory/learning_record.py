"""Append-only local learning events, separate from diagnostic episodes."""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ponytail: one process-wide lock is enough for Streamlit; use a file lock if multi-process writes matter.
_APPEND_LOCK = threading.Lock()
_BASE = {"kind", "event_id", "ts", "section", "filters"}
_FIELDS = {
    "reading_attempt": _BASE | {"stage", "attempt_answer", "attempt_correct"},
    "draft_submitted": _BASE | {"draft_id", "draft_text", "task_text", "review_scope", "revision_of", "submission_id"},
    "feedback_ready": _BASE | {"draft_id", "feedback"},
}


def _valid(row: dict) -> bool:
    kind = row.get("kind")
    if not isinstance(kind, str) or kind not in _FIELDS or set(row) != _FIELDS[kind]:
        return False
    if not isinstance(row["event_id"], str) or not row["event_id"]:
        return False
    try:
        stamp = datetime.fromisoformat(row["ts"])
    except (TypeError, ValueError):
        return False
    if stamp.tzinfo is None:
        return False
    section = row["section"]
    filters = row["filters"]
    if not isinstance(section, str) or section not in {"reading", "writing", "translation"} or not isinstance(filters, dict):
        return False
    needed = {"year", "month", "exam_set"} | ({"question_number"} if kind == "reading_attempt" else set())
    if set(filters) != needed or any(type(filters[key]) is not int for key in needed):
        return False
    if kind == "reading_attempt":
        return (section == "reading" and isinstance(row["stage"], str)
                and row["stage"] in {"attempt_correct", "attempt_wrong"}
                and type(row["attempt_correct"]) is bool
                and isinstance(row["attempt_answer"], str)
                and bool(row["attempt_answer"])
                and (row["stage"] == "attempt_correct") == row["attempt_correct"])
    if section == "reading":
        return False
    if kind == "draft_submitted":
        return (row["draft_id"] == row["event_id"]
                and isinstance(row["draft_text"], str) and bool(row["draft_text"].strip())
                and isinstance(row["task_text"], str) and bool(row["task_text"].strip())
                and isinstance(row["review_scope"], str)
                and row["review_scope"] in {"full", "language_only"}
                and (row["revision_of"] is None or isinstance(row["revision_of"], str))
                and isinstance(row["submission_id"], str) and bool(row["submission_id"]))
    return isinstance(row["draft_id"], str) and bool(row["draft_id"]) and isinstance(row["feedback"], dict)


class LearningRecord:
    def __init__(self, path: Path | None = None):
        if path is None:
            configured = os.environ.get("EXAM_TUTOR_LEARNING_PATH")
            if configured is not None:
                if not configured.strip() or not Path(configured).is_absolute():
                    raise ValueError("EXAM_TUTOR_LEARNING_PATH must be an absolute file path")
                path = Path(configured)
            else:
                path = Path.home() / ".exam-tutor" / "learning_events.jsonl"
        self.path = Path(path)

    def read(self) -> tuple[list[dict], list[str]]:
        if not self.path.exists():
            return [], []
        rows, warnings = [], []
        try:
            with self.path.open("rb") as handle:
                for line_number, raw in enumerate(handle, 1):
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        warnings.append(f"第{line_number}行不是有效 UTF-8 JSON，已跳过")
                        continue
                    if not isinstance(row, dict) or not _valid(row):
                        warnings.append(f"第{line_number}行字段无效，已跳过")
                        continue
                    rows.append(row)
        except OSError as exc:
            return [], [f"学习档案读取失败：{exc}"]
        return rows, warnings

    def append(self, event: dict) -> dict:
        if not isinstance(event, dict):
            raise ValueError("learning event must be a dict")
        row = {**event, "event_id": uuid.uuid4().hex, "ts": datetime.now(timezone.utc).isoformat()}
        if row.get("kind") == "draft_submitted":
            row["draft_id"] = row["event_id"]
        if not _valid(row):
            raise ValueError("invalid learning event")
        with _APPEND_LOCK:
            existing, warnings = self.read()
            if warnings and warnings[0].startswith("学习档案读取失败"):
                raise OSError(warnings[0])
            if row["kind"] == "draft_submitted":
                duplicate = next((old for old in existing if old["kind"] == "draft_submitted"
                                  and old["submission_id"] == row["submission_id"]), None)
                if duplicate:
                    return duplicate
            if row["kind"] == "feedback_ready":
                duplicate = next((old for old in existing if old["kind"] == "feedback_ready"
                                  and old["draft_id"] == row["draft_id"]), None)
                if duplicate:
                    return duplicate
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
