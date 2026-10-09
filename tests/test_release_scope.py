"""The public checkout excludes local content while retaining setup notes."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_git_upload_boundary_excludes_local_corpus_and_keeps_public_notes(tmp_path):
    (tmp_path / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"),
                                         encoding="utf-8")
    init = subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True, text=True)
    assert init.returncode == 0, init.stderr

    def ignored(path):
        result = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "--no-index", "--quiet", path],
                                capture_output=True, text=True)
        return result.returncode == 0

    for path in (
        "databases/试卷/original.pdf", "databases/ocr_pdfs/scan.pdf",
        "parsed_papers/2024_12_1.json", "episodes/private.jsonl",
        "translation_audit.md", ".planning/notes.md", ".superpowers/private.md",
        "docs/superpowers/plans/internal.md", "eval/ocr_spike/source.md",
        "eval/scenario_results.jsonl", "eval/smoke_results.jsonl",
        "tests/test_corpus_integrity.py",
        "tests/test_section_a_ocr.py",
    ):
        assert ignored(path), path
    for path in ("parsed_papers/README.md", "eval/cet6_skill_cases.json",
                 "eval/CET6_SKILL_EVAL.md", "README.md"):
        assert not ignored(path), path


def test_existing_git_index_contains_no_private_corpus():
    if not (ROOT / ".git").exists():
        return  # A source-only copy has no Git index yet.
    result = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", "ls-files"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    tracked = result.stdout.splitlines()
    private_prefixes = ("databases/", ".planning/", ".superpowers/", "docs/superpowers/",
                        "eval/ocr_spike/")
    private_exact = {"translation_audit.md", "tests/test_corpus_integrity.py",
                     "tests/test_section_a_ocr.py"}
    assert not [path for path in tracked if path.startswith(private_prefixes)
                or (path.startswith("parsed_papers/") and path != "parsed_papers/README.md")
                or (path.startswith("eval/") and path.endswith(".jsonl"))
                or path in private_exact]
