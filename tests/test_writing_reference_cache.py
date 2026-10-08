import json
from pathlib import Path
from unittest.mock import patch

from config import ragconfig
from retrieval.service import Service


def test_current_writing_cache_is_fail_closed(tmp_path):
    service = Service(ragconfig(), learning_path=tmp_path / "learning.jsonl")
    files = list((Path(__file__).resolve().parents[1] / "parsed_papers").glob("*.json"))
    assert len(files) == 38
    for path in files:
        paper = json.loads(path.read_text(encoding="utf-8"))
        assert paper.get("writing_needs_review") is not False
        with patch("retrieval.service.load_set_cached_only", return_value=paper):
            result = service.reference_material(2024, 12, 1, "writing", paper.get("writing", ""))
        assert result == {"status": "pending_review"}


def test_writing_reference_requires_both_fields_and_matching_task(tmp_path):
    service = Service(ragconfig(), learning_path=tmp_path / "learning.jsonl")
    paper = {"writing": "Original prompt", "writing_needs_review": False,
             "writing_sample": "Model essay", "writing_analysis": "中文解析"}
    with patch("retrieval.service.load_set_cached_only", return_value=paper):
        assert service.reference_material(2024, 12, 1, "writing", "Original\n prompt")["status"] == "ready"
        assert service.reference_material(2024, 12, 1, "writing", "Changed prompt")["status"] == "task_mismatch"
        paper["writing_analysis"] = ""
        assert service.reference_material(2024, 12, 1, "writing", "Original prompt") == {"status": "missing"}
        paper.pop("writing_needs_review")
        assert service.reference_material(2024, 12, 1, "writing", "Original prompt") == {"status": "pending_review"}
