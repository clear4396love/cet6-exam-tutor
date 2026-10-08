"""Local, append-only-by-revision chat files. Learning events live elsewhere."""

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from memory.session import FIELDS


_LOCK = threading.Lock()
_ID = re.compile(r"[0-9a-f]{32}\Z")
_MAX_FILE = 10_000_000


class ChatConflict(RuntimeError):
    """The chat changed since this tab last loaded it."""


def valid_location(location: dict) -> bool:
    return (isinstance(location, dict) and set(location) <= set(FIELDS)
            and all(value is not None and
                    (type(value) is int if key != "section" else isinstance(value, str) and value in {"reading", "writing", "translation"})
                    for key, value in location.items()))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid(row: dict, expected_id: str) -> bool:
    fields = {"id", "title", "created_at", "updated_at", "revision", "parent_id", "fork_turn", "turns"}
    if not isinstance(row, dict) or set(row) != fields or row.get("id") != expected_id:
        return False
    if not isinstance(row.get("title"), str) or not row["title"] or len(row["title"]) > 30:
        return False
    if type(row.get("revision")) is not int or row["revision"] < 0:
        return False
    if not all(isinstance(row.get(k), str) for k in ("created_at", "updated_at")):
        return False
    try:
        if any(datetime.fromisoformat(row[key]).tzinfo is None for key in ("created_at", "updated_at")):
            return False
    except ValueError:
        return False
    if row.get("parent_id") is not None and (not isinstance(row["parent_id"], str) or not _ID.fullmatch(row["parent_id"])):
        return False
    if row.get("fork_turn") is not None and (type(row["fork_turn"]) is not int or row["fork_turn"] < 0):
        return False
    turns = row.get("turns")
    return (isinstance(turns, list) and len(turns) == row["revision"]
            and all(isinstance(turn, dict) and set(turn) == {"user", "assistant", "location"}
                    and isinstance(turn["user"], str) and len(turn["user"]) <= 500
                    and isinstance(turn["assistant"], str) and len(turn["assistant"]) <= 50_000
                    and valid_location(turn["location"]) for turn in turns))


class ChatArchive:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, thread_id: str) -> Path:
        if not isinstance(thread_id, str) or not _ID.fullmatch(thread_id):
            raise ValueError("invalid chat ID")
        return self.root / f"{thread_id}.json"

    def _write(self, row: dict) -> None:
        payload = json.dumps(row, ensure_ascii=False)
        if len(payload.encode("utf-8")) > _MAX_FILE:
            raise ValueError("chat file too large")
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".chat-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(name, self._path(row["id"]))
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def create(self) -> dict:
        stamp = _now()
        row = {"id": uuid.uuid4().hex, "title": "新对话", "created_at": stamp,
               "updated_at": stamp, "revision": 0, "parent_id": None,
               "fork_turn": None, "turns": []}
        with _LOCK:
            self._write(row)
        return row

    def load(self, thread_id: str) -> dict | None:
        path = self._path(thread_id)
        try:
            if not path.exists():
                return None
            if path.is_symlink():
                raise ValueError("chat link not allowed")
            if path.stat().st_size > _MAX_FILE:
                raise ValueError("chat file too large")
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("chat file unreadable") from exc
        if not _valid(row, thread_id):
            raise ValueError("chat file invalid")
        return row

    def list_threads(self) -> tuple[list[dict], list[str]]:
        items, warnings = [], []
        if not self.root.exists():
            return items, warnings
        for path in self.root.glob("*.json"):
            try:
                row = self.load(path.stem)
                if row is not None:
                    items.append({key: row[key] for key in ("id", "title", "created_at", "updated_at", "revision", "parent_id", "fork_turn")})
            except ValueError:
                warnings.append(f"聊天存档 {path.name} 无法读取，已跳过")
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items, warnings

    def append_turn(self, thread_id: str, user: str, assistant: str,
                    location: dict, expected_revision: int) -> dict:
        if not isinstance(user, str) or len(user) > 500 or not isinstance(assistant, str) or len(assistant) > 50_000 or not valid_location(location):
            raise ValueError("invalid chat turn")
        with _LOCK:
            row = self.load(thread_id)
            if row is None:
                raise ValueError("chat not found")
            if row["revision"] != expected_revision:
                raise ChatConflict("chat changed in another tab")
            row["turns"].append({"user": user, "assistant": assistant, "location": dict(location)})
            row["revision"] += 1
            row["updated_at"] = _now()
            if row["revision"] == 1:
                row["title"] = user.strip()[:30] or "新对话"
            self._write(row)
            return row

    def fork(self, thread_id: str, through_turn: int) -> dict:
        with _LOCK:
            parent = self.load(thread_id)
            if parent is None or type(through_turn) is not int or not 0 <= through_turn <= len(parent["turns"]):
                raise ValueError("invalid fork point")
            stamp = _now()
            turns = parent["turns"][:through_turn]
            row = {"id": uuid.uuid4().hex, "title": parent["title"] if turns else "新对话",
                   "created_at": stamp, "updated_at": stamp, "revision": len(turns),
                   "parent_id": thread_id, "fork_turn": through_turn, "turns": turns}
            self._write(row)
            return row
