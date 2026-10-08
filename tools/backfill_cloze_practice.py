"""Recover Section A blank positions from local sources, without online OCR."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reading"))

from paddle_ocr import clean
from sectionA_load import Cloze_Passage


NUMBERS = [str(number) for number in range(26, 36)]
LETTERS = set("ABCDEFGHIJKLMNO")
MARKER = re.compile(r"\{\{(\d+)\}\}")


def _normalized(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def _local_pages(pdf: Path, ocr_dir: Path) -> list:
    folder = ocr_dir / f"{pdf.stem}_paddle"
    meta_path = folder / "meta.json"
    if meta_path.is_file():
        try:
            count = json.loads(meta_path.read_text(encoding="utf-8"))["pages"]
            files = sorted(folder.glob("doc_*.md"))
            if isinstance(count, int) and count > 0 and len(files) == count:
                return [SimpleNamespace(page_content=clean(path.read_text(encoding="utf-8")))
                        for path in files]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if pdf.is_file():
        try:
            with fitz.open(pdf) as document:
                pages = [SimpleNamespace(page_content=page.get_text()) for page in document]
            if any(page.page_content.strip() for page in pages):
                return pages
        except (OSError, ValueError, RuntimeError):
            pass
    return []


def backfill_one(
    cache_path: Path, pdf_dir: Path, ocr_dir: Path, *, write: bool = False,
) -> tuple[bool, str]:
    """Validate one existing cache; optionally add only section_a.practice_text."""
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "缓存不可读"
    section = data.get("section_a") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        return False, "没有选词填空缓存"
    words, questions, body = section.get("words"), section.get("questions"), section.get("text")
    if (not isinstance(words, dict) or set(words) != LETTERS
            or not isinstance(questions, dict) or not isinstance(body, str)):
        return False, "词库、题目或正文不完整"
    for number in NUMBERS:
        item = questions.get(number)
        if not isinstance(item, dict) or item.get("answer") not in LETTERS:
            return False, f"第 {number} 空缺少 KEYS"
        if words[item["answer"]] != item.get("answer_word"):
            return False, f"第 {number} 空答案与词库不符"

    pdf = pdf_dir / f"CET6_{data.get('year')}年{data.get('month')}月_第{data.get('exam_set')}套_真题.pdf"
    pages = _local_pages(pdf, ocr_dir)
    if not pages:
        return False, "没有可读的本地 OCR 或 PDF 文字层"
    parser = Cloze_Passage()
    keys = {int(number): questions[number]["answer"] for number in NUMBERS}
    try:
        chunks = parser.split_passages(parser.define(pages))
        candidates = [parser.parse_passage(chunk, keys) for chunk in chunks]
    except (AttributeError, IndexError, TypeError, ValueError):
        return False, "本地原文无法解析"
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("words") != words:
            continue
        practice = candidate.get("practice_text")
        if not isinstance(practice, str) or MARKER.findall(practice) != NUMBERS:
            continue
        if _normalized(MARKER.sub("", practice)) != _normalized(body):
            continue
        existing = section.get("practice_text")
        if existing is not None and existing != practice:
            return False, "已有练习原文与本地来源不一致"
        if write and existing is None:
            section["practice_text"] = practice
            content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=cache_path.parent, suffix=".cloze-tmp", delete=False,
            ) as temporary:
                temporary.write(content)
                temporary_path = Path(temporary.name)
            try:
                os.replace(temporary_path, cache_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        return True, "已核验" if existing is not None else "已回填" if write else "可回填"
    return False, "空位、原文或词库与缓存不一致"


def main() -> None:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--write", action="store_true", help="核验后写入 practice_text；默认只预演")
    args = command.parse_args()
    files = sorted((ROOT / "parsed_papers").glob("*.json"))
    pdf_dir = ROOT / "databases" / "试卷"
    ocr_dir = ROOT / "databases" / "ocr_pdfs"
    ready = skipped = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "section_a" not in data:
            continue
        ok, reason = backfill_one(path, pdf_dir, ocr_dir, write=args.write)
        ready += ok
        skipped += not ok
        print(f"{path.name}: {reason}")
    print(f"可练 {ready} 套；跳过 {skipped} 套；模式：{'写入' if args.write else '预演'}")


if __name__ == "__main__":
    main()
