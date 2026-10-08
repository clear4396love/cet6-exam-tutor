from pathlib import Path

from tests.conftest import _snapshot_private_path


def test_snapshot_detects_same_size_edits(tmp_path: Path):
    target = tmp_path / "private.jsonl"
    target.write_bytes(b"first")
    before = _snapshot_private_path(target)
    target.write_bytes(b"other")
    assert before != _snapshot_private_path(target)


def test_snapshot_detects_directory_addition_and_removal(tmp_path: Path):
    directory = tmp_path / "chats"
    before = _snapshot_private_path(directory)
    directory.mkdir()
    assert before != _snapshot_private_path(directory)
    target = directory / "one.json"
    target.write_text("{}", encoding="utf-8")
    with_file = _snapshot_private_path(directory)
    assert before != with_file
    target.unlink()
    assert with_file != _snapshot_private_path(directory)
