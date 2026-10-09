"""翻译试译的缓存与问答边界：待核内容不能发给学生。"""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from memory.episode import Episode
from retrieval.service import Service


ROOT = Path(__file__).resolve().parents[1]
PENDING = {"2020_9_1", "2021_12_2", "2021_12_3", "2022_12_1", "2025_6_1"}


class OfflineIntent:
    def __init__(self, config):
        pass

    def merged(self, user_message, table):
        if user_message == "翻译呢":
            return "FOLLOW_UP", {}, False
        return "NEW_QUESTION", {}, False


def _ask(message):
    with tempfile.TemporaryDirectory() as directory:
        service = Service(config=None)
        service.episode = Episode(out_dir=directory)
        with patch("retrieval.service.Find_Intent", OfflineIntent):
            reply = service.process(message)
        return reply, service.episode.lines()[0]


@pytest.mark.local_corpus
def test_translation_samples_are_cached_and_pending_ones_are_marked():
    files = sorted((ROOT / "parsed_papers").glob("*.json"))
    assert len(files) == 38
    for path in files:
        paper = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(paper["translation"], str) and paper["translation"].strip()
        assert isinstance(paper["translation_sample"], str) and paper["translation_sample"].strip()
        assert paper["translation_needs_review"] is (path.stem in PENDING)


@pytest.mark.local_corpus
def test_all_cached_translation_analyses_match_the_reviewed_explanations():
    audit = (ROOT / "translation_audit.md").read_text(encoding="utf-8")
    explanations = dict(re.findall(
        r"(?ms)^### (\d{4}_\d{1,2}_\d+)｜.*?^#### 逐句解析(?:（样例）)?\n\n(.*?)(?=^### |\Z)",
        audit,
    ))
    assert len(explanations) == 38
    for path in (ROOT / "parsed_papers").glob("*.json"):
        paper = json.loads(path.read_text(encoding="utf-8"))
        assert paper["translation_analysis"] == explanations[path.stem].strip()


@pytest.mark.local_corpus
def test_translation_question_shows_original_and_non_official_sample():
    reply, trace = _ask("2024年12月第1套翻译怎么写")

    assert "北斗" in reply
    assert "Beidou" in reply
    assert "练习参考译文" in reply and "非官方答案" in reply
    assert trace["stage"] == "translation_sample"
    assert trace["hit"] is True
    assert trace["retrieved_doc_ids"] == ["2024_12_1"]


@pytest.mark.local_corpus
def test_pending_translation_is_not_shown_to_student():
    reply, trace = _ask("2020年9月第1套翻译怎么写")

    assert "待核" in reply
    assert "Journey to the West" not in reply
    assert trace["stage"] == "translation_pending_review"
    assert trace["hit"] is False


def test_translation_requires_full_paper_and_existing_cache():
    missing, missing_trace = _ask("2024年12月翻译怎么写")
    absent, absent_trace = _ask("2029年12月第1套翻译怎么写")

    assert "套" in missing and missing_trace["stage"] == "missing_paper"
    assert "未定位到原题" in absent
    assert absent_trace["stage"] == "cache_miss_paper"


@pytest.mark.local_corpus
def test_switching_between_translation_and_reading_does_not_keep_stale_section():
    with tempfile.TemporaryDirectory() as directory:
        service = Service(config=None)
        service.episode = Episode(out_dir=directory)
        with patch("retrieval.service.Find_Intent", OfflineIntent):
            first = service.process("2024年12月第1套翻译怎么写")
            second = service.process("第43题呢")
            third = service.process("翻译呢")
        stages = [row["stage"] for row in service.episode.lines()]

    assert "Beidou" in first
    assert "第43题答案" in second
    assert "Beidou" in third
    assert stages == [
        "translation_sample", "answer", "translation_sample"
    ]
