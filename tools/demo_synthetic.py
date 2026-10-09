"""Offline, invented-data demonstration of answer-free practice and grading."""

import argparse
import json
from pathlib import Path

from retrieval.practice import get_practice_item, grade_attempt


PAPER = Path(__file__).resolve().parents[1] / "examples" / "synthetic_paper.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合成示例，非真题；不需要 DeepSeek 或真题缓存")
    parser.add_argument("--answer", help="提交 A、B、C 或 D 后显示判分")
    args = parser.parse_args(argv)
    paper = json.loads(PAPER.read_text(encoding="utf-8"))
    item = get_practice_item(paper, 46)
    if item is None:
        print("合成示例不可用")
        return 1

    print("合成示例，非真题")
    print(item["passage_text"])
    print(item["stem"])
    for letter, option in item["options"].items():
        print(f"{letter}. {option}")

    if args.answer is not None:
        result = grade_attempt(paper, 46, args.answer)
        if result is None:
            print("请提交 A、B、C 或 D")
            return 2
        print(f"你的答案：{result['submitted']}；正确答案：{result['answer']}；"
              f"{'答对' if result['correct'] else '答错'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
