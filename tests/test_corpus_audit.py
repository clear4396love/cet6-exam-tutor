"""Source scope is declared independently of what parsing happened to recover."""

import json

from tools.corpus_audit import audit_cache


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_source_declared_sections_expose_missing_cache_sections(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2022_6_2.json", {"year": 2022, "month": 6, "exam_set": 2})
    scope = tmp_path / "scope.json"
    _write(scope, {"2022_6_2": {"expected_reading": ["A", "B", "C"], "source": "source.pdf"}})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["missing_sections"] == ["A", "B", "C"]
    assert report["papers"][0]["scope_status"] == "verified"
    assert report["papers"][0]["source"] == "source.pdf"
    assert report["missing_count"] == 3


def test_source_declared_paper_without_cache_is_reported(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    scope = tmp_path / "scope.json"
    _write(scope, {"2022_6_2": {"expected_reading": ["A", "B", "C"],
                                  "source": "source.pdf"}})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["paper"] == "2022_6_2"
    assert report["papers"][0]["missing_sections"] == ["A", "B", "C"]
    assert report["missing_count"] == 3


def test_shared_reading_is_not_reported_as_missing(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2022_9_2.json", {"year": 2022, "month": 9, "exam_set": 2})
    scope = tmp_path / "scope.json"
    _write(scope, {"2022_9_2": {"expected_reading": [], "source": "source.pdf"}})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["missing_sections"] == []
    assert report["papers"][0]["scope_status"] == "verified"
    assert report["missing_count"] == 0


def test_undeclared_scope_stays_unknown_instead_of_being_inferred(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2024_12_1.json", {"year": 2024, "month": 12, "exam_set": 1})
    scope = tmp_path / "scope.json"
    _write(scope, {})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["scope_status"] == "unknown"
    assert report["papers"][0]["missing_sections"] == []
    assert report["unknown_count"] == 1


def test_present_section_without_keys_is_invalid_not_complete(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2024_12_1.json", {"year": 2024, "month": 12, "exam_set": 1,
                                      "questions": {str(n): {"stem": "A question", "answer": None}
                                                    for n in range(36, 46)},
                                      "paragraphs": {"A": "A passage"}})
    scope = tmp_path / "scope.json"
    _write(scope, {"2024_12_1": {"expected_reading": ["B"], "source": "source.pdf"}})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["invalid_sections"] == ["B"]
    assert report["papers"][0]["missing_sections"] == []
    assert report["invalid_count"] == 1


def test_unknown_source_scope_still_reports_present_but_invalid_section(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2024_12_1.json", {"year": 2024, "month": 12, "exam_set": 1,
                                      "questions": {"36": {"stem": "Question", "answer": None}},
                                      "paragraphs": {"A": "Passage"}})
    scope = tmp_path / "scope.json"
    _write(scope, {})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["scope_status"] == "unknown"
    assert report["papers"][0]["invalid_sections"] == ["B"]
    assert report["invalid_count"] == 1


def test_cloze_with_only_one_word_is_invalid_even_if_ten_answers_exist(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2024_12_1.json", {"section_a": {
        "text": "A cloze passage", "words": {"A": "word"},
        "questions": {str(n): {"answer": "A", "answer_word": "word"}
                      for n in range(26, 36)},
    }})
    scope = tmp_path / "scope.json"
    _write(scope, {"2024_12_1": {"expected_reading": ["A"], "source": "source.pdf"}})

    report = audit_cache(cache, scope)

    assert report["papers"][0]["invalid_sections"] == ["A"]


def test_audit_reports_writing_and_ocr_metadata_without_calling_them_reading_failures(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    _write(cache / "2024_12_1.json", {"year": 2024, "month": 12, "exam_set": 1,
                                      "writing_directions": "Write an essay.", "ocr_verified": True})
    _write(cache / "2024_12_2.json", {"year": 2024, "month": 12, "exam_set": 2})
    scope = tmp_path / "scope.json"
    _write(scope, {})

    report = audit_cache(cache, scope)

    assert report["writing_directions_count"] == 1
    assert report["ocr_verified_count"] == 1
    assert report["missing_count"] == report["invalid_count"] == 0
