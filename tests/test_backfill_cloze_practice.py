"""Offline cloze backfill must only add verified blank positions."""

import json
from pathlib import Path

import fitz
import pytest

from tools.backfill_cloze_practice import backfill_one


LETTERS = "ABCDEFGHIJKLMNO"
WORDS = {letter: f"word{letter.lower()}" for letter in LETTERS}
ANSWERS = {str(n): {"answer": LETTERS[n - 26], "answer_word": WORDS[LETTERS[n - 26]]}
           for n in range(26, 36)}
BANK = " ".join(f"{letter}) {word}" for letter, word in WORDS.items())
PASSAGE = " ".join(f"word $ \\underline{{{n}}} $" for n in range(26, 36))
SOURCE = (
    "Part III\nReading Comprehension\nSection A\n"
    "You may not use any of the words in the bank more than once.\n"
    f"{PASSAGE}\n{BANK}\nSection B\n"
)


def _paths(tmp_path: Path):
    cache = tmp_path / "parsed_papers" / "2021_12_1.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({
        "year": 2021, "month": 12, "exam_set": 1,
        "section_a": {"text": " ".join("word" for _ in range(10)),
                      "words": WORDS, "questions": ANSWERS},
        "writing": "keep me",
    }), encoding="utf-8")
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    ocr_dir = tmp_path / "ocr"
    ocr_dir.mkdir()
    return cache, pdf_dir, ocr_dir


def _ocr(ocr_dir: Path, source: str = SOURCE):
    folder = ocr_dir / "CET6_2021年12月_第1套_真题_paddle"
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"pages": 1}), encoding="utf-8")
    (folder / "doc_000.md").write_text(source, encoding="utf-8")


def test_backfill_uses_only_local_ocr_and_preserves_other_fields(tmp_path):
    cache, pdf_dir, ocr_dir = _paths(tmp_path)
    _ocr(ocr_dir)
    before = cache.read_bytes()

    assert backfill_one(cache, pdf_dir, ocr_dir)[0] is True
    assert cache.read_bytes() == before
    assert backfill_one(cache, pdf_dir, ocr_dir, write=True)[0] is True
    written = json.loads(cache.read_text(encoding="utf-8"))
    assert written["writing"] == "keep me"
    assert written["section_a"]["text"] == " ".join("word" for _ in range(10))
    assert written["section_a"]["questions"] == ANSWERS
    assert written["section_a"]["practice_text"] == " ".join(
        f"word {{{{{n}}}}}" for n in range(26, 36)
    )
    once = cache.read_bytes()
    assert backfill_one(cache, pdf_dir, ocr_dir, write=True)[0] is True
    assert cache.read_bytes() == once


@pytest.mark.parametrize("source", [
    SOURCE.replace("$ \\underline{28} $", "$ \\underline{27} $"),
    SOURCE.replace("$ \\underline{28} $", "SWAP").replace(
        "$ \\underline{29} $", "$ \\underline{28} $").replace(
        "SWAP", "$ \\underline{29} $"),
])
def test_backfill_skips_duplicate_or_disordered_blanks(tmp_path, source):
    cache, pdf_dir, ocr_dir = _paths(tmp_path)
    _ocr(ocr_dir, source)
    before = cache.read_bytes()

    ok, reason = backfill_one(cache, pdf_dir, ocr_dir, write=True)

    assert ok is False
    assert reason
    assert cache.read_bytes() == before


def test_backfill_skips_source_word_bank_mismatch(tmp_path):
    cache, pdf_dir, ocr_dir = _paths(tmp_path)
    _ocr(ocr_dir, SOURCE.replace("A) worda", "A) different"))
    before = cache.read_bytes()

    ok, reason = backfill_one(cache, pdf_dir, ocr_dir, write=True)

    assert ok is False
    assert reason
    assert cache.read_bytes() == before


def test_backfill_reads_local_pdf_text_when_ocr_missing(tmp_path):
    cache, pdf_dir, ocr_dir = _paths(tmp_path)
    pdf = pdf_dir / "CET6_2021年12月_第1套_真题.pdf"
    source = SOURCE.replace(PASSAGE, " ".join(f"word {n}" for n in range(26, 36)))
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), source, fontsize=8)
    document.save(pdf)
    document.close()

    ok, reason = backfill_one(cache, pdf_dir, ocr_dir, write=True)

    assert ok is True, reason
    assert "{{26}}" in json.loads(cache.read_text(encoding="utf-8"))["section_a"]["practice_text"]


def test_backfill_skips_missing_or_unreadable_local_source_without_network(tmp_path, monkeypatch):
    cache, pdf_dir, ocr_dir = _paths(tmp_path)
    before = cache.read_bytes()
    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: pytest.fail("network OCR called"))

    assert backfill_one(cache, pdf_dir, ocr_dir, write=True)[0] is False
    assert cache.read_bytes() == before

    pdf = pdf_dir / "CET6_2021年12月_第1套_真题.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf)
    document.close()
    assert backfill_one(cache, pdf_dir, ocr_dir, write=True)[0] is False
    assert cache.read_bytes() == before
