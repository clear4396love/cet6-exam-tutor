import pytest

from memory.chat_archive import ChatArchive, ChatConflict


def test_chat_archive_round_trip_and_fork(tmp_path):
    archive = ChatArchive(tmp_path / "chats")
    original = archive.create()
    assert original["title"] == "新对话"
    saved = archive.append_turn(original["id"], "  第一题怎么做？  ", "解析一", {"year": 2024, "question_number": 43}, 0)
    saved = archive.append_turn(original["id"], "追问", "解析二", {"year": 2024}, 1)
    assert saved["title"] == "第一题怎么做？"
    assert ChatArchive(tmp_path / "chats").load(original["id"])["turns"][1]["assistant"] == "解析二"
    before = (tmp_path / "chats" / f"{original['id']}.json").read_bytes()
    forked = archive.fork(original["id"], 1)
    assert len(forked["turns"]) == 1
    assert forked["parent_id"] == original["id"]
    assert (tmp_path / "chats" / f"{original['id']}.json").read_bytes() == before
    assert len(archive.list_threads()[0]) == 2


def test_chat_archive_rejects_conflicts_bad_inputs_and_skips_corruption(tmp_path):
    archive = ChatArchive(tmp_path / "chats")
    thread = archive.create()
    archive.append_turn(thread["id"], "hi", "hello", {}, 0)
    with pytest.raises(ChatConflict):
        ChatArchive(tmp_path / "chats").append_turn(thread["id"], "stale", "reply", {}, 0)
    with pytest.raises(ValueError):
        archive.load("../bad")
    with pytest.raises(ValueError):
        archive.append_turn(thread["id"], "x", "y", {"answer": "A"}, 1)
    with pytest.raises(ValueError):
        archive.append_turn(thread["id"], "x", "y", {"year": True}, 1)
    with pytest.raises(ValueError):
        archive.append_turn(thread["id"], "x" * 501, "y", {}, 1)
    with pytest.raises(ValueError):
        archive.append_turn(thread["id"], "x", "y" * 50_001, {}, 1)
    (tmp_path / "chats" / ("f" * 32 + ".json")).write_text("broken", encoding="utf-8")
    items, warnings = archive.list_threads()
    assert len(items) == 1 and warnings
    assert (tmp_path / "chats" / ("f" * 32 + ".json")).exists()
