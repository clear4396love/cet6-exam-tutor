import hashlib
import os
import tempfile
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items):
    root = Path(__file__).resolve().parents[1]
    cache = root / "parsed_papers"
    has_cache = len(list(cache.glob("*.json"))) == 38
    has_audit = (root / "translation_audit.md").exists()
    for item in items:
        if "local_corpus" in item.keywords and not has_cache:
            item.add_marker(pytest.mark.skip(reason="requires the 38-paper cache"))
        elif "local_audit" in item.keywords and not has_audit:
            item.add_marker(pytest.mark.skip(reason="requires the maintainer's private translation audit"))


@pytest.fixture(scope="session", autouse=True)
def writable_python_temp(tmp_path_factory):
    temp_root = tmp_path_factory.getbasetemp() / "python-temp"
    temp_root.mkdir()
    previous_dir = tempfile.tempdir
    previous_env = {name: os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")}
    tempfile.tempdir = str(temp_root)
    for name in previous_env:
        os.environ[name] = str(temp_root)
    try:
        yield
    finally:
        tempfile.tempdir = previous_dir
        for name, previous in previous_env.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


def _snapshot_private_path(path: Path) -> tuple[bool, tuple[tuple[str, str], ...]]:
    if not path.exists():
        return False, ()
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    return True, tuple(
        (("." if path.is_file() else item.relative_to(path).as_posix()),
         hashlib.sha256(item.read_bytes()).hexdigest())
        for item in files
    )


@pytest.fixture(autouse=True)
def isolate_learning_record(tmp_path, monkeypatch):
    real_archive = Path.home() / ".exam-tutor" / "learning_events.jsonl"
    real_chats = real_archive.parent / "chats"
    before_archive = _snapshot_private_path(real_archive)
    before_chats = _snapshot_private_path(real_chats)
    monkeypatch.setenv("EXAM_TUTOR_LEARNING_PATH", str(tmp_path / "learning_events.jsonl"))
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    yield
    assert _snapshot_private_path(real_archive) == before_archive, "tests changed the user's learning archive"
    assert _snapshot_private_path(real_chats) == before_chats, "tests changed the user's chat archive"
