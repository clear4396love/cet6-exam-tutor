import json
from pathlib import Path


CACHE_DIR = Path(__file__).resolve().parents[1] / "parsed_papers"


def _paper(name: str) -> dict:
    return json.loads((CACHE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_repaired_section_b_paragraphs_match_source_text():
    paper = _paper("2022_12_3")
    assert "many commenters" in paper["paragraphs"]["D"]
    assert "Allison Vulgamore" in paper["paragraphs"]["I"]
    assert paper["questions"]["40"]["answer"] == "D"

    paper = _paper("2020_12_1")
    assert "United States' Midwest region" in paper["paragraphs"]["M"]

    split_paragraphs = {
        "2020_12_1": {"I": "In 2011, IBM", "O": "Practically, to say"},
        "2020_12_3": {"I": "In addition to technical", "O": "Europe has many scenarios"},
        "2021_12_1": {"I": "In a statement, Burberry"},
        "2022_6_2": {"I": "We need stories and histories"},
        "2023_3_1": {"I": "San Francisco and the Bay Area"},
    }
    for name, expected in split_paragraphs.items():
        paragraphs = _paper(name)["paragraphs"]
        for letter, opening in expected.items():
            assert paragraphs[letter].startswith(opening), f"{name} {letter} 段未正确拆分"
