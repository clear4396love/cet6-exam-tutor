"""The public demo uses invented text and needs no private exam cache."""

import json
from pathlib import Path

from tools.demo_synthetic import main


ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_fixture_is_answer_free_until_graded(capsys):
    paper = json.loads((ROOT / "examples" / "synthetic_paper.json").read_text(encoding="utf-8"))
    assert paper["synthetic"] is True
    assert paper["section_c"]["passages"][0]["questions"]["46"]["answer"] == "B"

    assert main([]) == 0
    question = capsys.readouterr().out
    assert "合成示例，非真题" in question
    assert "Which place did the group visit?" in question
    assert "正确答案" not in question

    assert main(["--answer", "B"]) == 0
    feedback = capsys.readouterr().out
    assert "正确答案：B" in feedback
    assert "答对" in feedback
