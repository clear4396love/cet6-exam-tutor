"""Read-only audit of source scope and answerability, not full passage fidelity."""

import argparse
import json
from pathlib import Path

from retrieval.practice import get_practice_item
from retrieval.structured import get_section_a_answer


ROOT = Path(__file__).resolve().parents[1]
RANGES = {"A": range(26, 36), "B": range(36, 46), "C": range(46, 56)}


def _section_state(paper: dict, section: str) -> str:
    if section == "A":
        data = paper.get("section_a")
        if not isinstance(data, dict) or not data.get("questions"):
            return "missing"
        body = data.get("text")
        words = data.get("words")
        complete = (isinstance(body, str) and bool(body.strip())
                    and isinstance(words, dict)
                    and set(words) == set("ABCDEFGHIJKLMNO")
                    and all(get_section_a_answer(paper, n) is not None
                            for n in RANGES[section]))
    elif section == "B":
        if not paper.get("questions") and not paper.get("paragraphs"):
            return "missing"
        complete = all(get_practice_item(paper, n) is not None for n in RANGES[section])
    else:
        data = paper.get("section_c")
        if not isinstance(data, dict) or not data.get("passages"):
            return "missing"
        complete = all(get_practice_item(paper, n) is not None for n in RANGES[section])
    return "answerable" if complete else "invalid"


def audit_cache(cache_dir: Path, scope_path: Path) -> dict:
    """Unknown source scope stays unknown; cached data never declares its own scope."""
    scopes = json.loads(scope_path.read_text(encoding="utf-8"))
    rows = []
    writing_directions_count = 0
    ocr_verified_count = 0
    cached = {path.stem: path for path in cache_dir.glob("*.json")}
    for paper_id in sorted(cached.keys() | scopes.keys()):
        path = cached.get(paper_id)
        paper = json.loads(path.read_text(encoding="utf-8")) if path is not None else {}
        writing_directions_count += "writing_directions" in paper
        ocr_verified_count += "ocr_verified" in paper
        declaration = scopes.get(paper_id)
        expected = declaration["expected_reading"] if declaration is not None else None
        states = {section: _section_state(paper, section) for section in RANGES}
        rows.append({
            "paper": paper_id,
            "scope_status": "verified" if expected is not None else "unknown",
            "source": declaration["source"] if declaration is not None else None,
            "expected_reading": expected,
            "section_states": states,
            "missing_sections": [name for name in (expected or []) if states[name] == "missing"],
            "invalid_sections": [name for name in RANGES if states[name] == "invalid"],
        })
    return {
        "papers": rows,
        "missing_count": sum(len(row["missing_sections"]) for row in rows),
        "invalid_count": sum(len(row["invalid_sections"]) for row in rows),
        "unknown_count": sum(row["scope_status"] == "unknown" for row in rows),
        "writing_directions_count": writing_directions_count,
        "ocr_verified_count": ocr_verified_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="对照已核实的原卷板块范围，审计阅读缓存。")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "parsed_papers")
    parser.add_argument("--scope", type=Path, default=ROOT / "tools" / "corpus_scope.json")
    args = parser.parse_args(argv)
    report = audit_cache(args.cache_dir, args.scope)
    for row in report["papers"]:
        if row["missing_sections"] or row["invalid_sections"]:
            print(f"{row['paper']}: 缺失={','.join(row['missing_sections']) or '-'} "
                  f"无效={','.join(row['invalid_sections']) or '-'} "
                  f"原卷={row['source'] or '未核实'}")
    print(f"共 {len(report['papers'])} 套；原卷范围未核实 {report['unknown_count']} 套；"
          f"已核实范围内缺失 {report['missing_count']} 块，现有板块无效 {report['invalid_count']} 块；"
          f"写作说明字段 {report['writing_directions_count']} 套，"
          f"OCR 核验字段 {report['ocr_verified_count']} 套。")
    return int(bool(report["missing_count"] or report["invalid_count"]))


if __name__ == "__main__":
    raise SystemExit(main())
