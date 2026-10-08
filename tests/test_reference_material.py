from unittest.mock import patch

from config import ragconfig
from retrieval.service import Service


def test_reference_material_review_and_task_match(tmp_path):
    service = Service(ragconfig(), learning_path=tmp_path / "learning.jsonl")
    paper = {"translation": "中文 原文", "translation_needs_review": False,
             "translation_sample": "Reference translation", "translation_analysis": "中文解析",
             "writing": "Essay topic", "writing_needs_review": False,
             "writing_sample": "Model essay", "writing_analysis": "作文解析"}
    with patch("retrieval.service.load_set_cached_only", return_value=paper):
        assert service.reference_material(2024, 12, 1, "translation", "中文\n原文")["status"] == "ready"
        assert service.reference_material(2024, 12, 1, "translation", "别的题目")["status"] == "task_mismatch"
        assert service.reference_material(2024, 12, 1, "writing", "Essay topic")["sample"] == "Model essay"
        paper["writing_needs_review"] = True
        assert service.reference_material(2024, 12, 1, "writing", "Essay topic")["status"] == "pending_review"
        paper["translation_needs_review"] = True
        assert service.reference_material(2024, 12, 1, "translation", "中文 原文")["status"] == "pending_review"
