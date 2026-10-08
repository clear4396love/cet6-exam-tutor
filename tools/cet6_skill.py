"""Single-shot entrypoint for the repo-scoped Codex Skill."""

import argparse
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from config import ragconfig
from memory.learning_record import LearningRecord
from retrieval.locator import parse_conditions
from retrieval.practice import summarize_learning
from retrieval.service import Service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cached CET-6 tutor and local writing practice")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("progress", help="Read writing/translation progress without draft text")
    ask = commands.add_parser("ask", help="Ask one full-coordinate CET-6 question")
    ask.add_argument("question")
    for name in ("task", "submit", "reference"):
        command = commands.add_parser(name)
        command.add_argument("year", type=int)
        command.add_argument("month", type=int)
        command.add_argument("exam_set", type=int)
        command.add_argument("section", choices=("writing", "translation"))
        if name == "submit":
            command.add_argument("--text-file", required=True, type=Path)
            command.add_argument("--revision-of")
        if name == "reference":
            command.add_argument("--confirm", action="store_true", required=True)
    review = commands.add_parser("review", help="Retry feedback for a saved draft")
    review.add_argument("draft_id")
    history = commands.add_parser("history", help="Read saved drafts and feedback")
    history.add_argument("--section", choices=("writing", "translation"))
    args = parser.parse_args(argv)

    if args.command == "ask":
        position = parse_conditions(args.question)
        if (position.get("question_number") not in range(26, 56)
                or position.get("section") in {"writing", "translation", "listening"}):
            print(json.dumps({"status": "unsupported", "message": "ask 仅用于第 26～55 题阅读题；作文和翻译请使用专用命令。"},
                             ensure_ascii=False))
            return 2
        print(Service(ragconfig(), cached_only=True).process(args.question))
        return 0

    if args.command in {"task", "submit", "review", "history", "reference"}:
        if args.command == "submit":
            try:
                draft_text = args.text_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                print(json.dumps({"status": "input_error", "message": str(exc)}, ensure_ascii=False))
                return 1
        service = Service(ragconfig(), cached_only=True)
        if args.command == "task":
            task = service.draft_question(args.year, args.month, args.exam_set, args.section)
            result = {"status": "ready", **task} if task else {"status": "unavailable"}
        elif args.command == "submit":
            saved = service.submit_draft(args.year, args.month, args.exam_set, args.section,
                                         draft_text, revision_of=args.revision_of)
            if saved["status"] == "saved":
                with redirect_stdout(sys.stderr):
                    review_result = service.review_draft(saved["draft_id"])
                result = {"draft_id": saved["draft_id"], **review_result}
            else:
                result = saved
        elif args.command == "review":
            with redirect_stdout(sys.stderr):
                result = service.review_draft(args.draft_id)
        elif args.command == "history":
            archive = LearningRecord()
            _, warnings = archive.read()
            result = {"status": "no_archive" if not archive.path.exists() else "partial" if warnings else "ready",
                      "drafts": service.draft_history(args.section), "history_warnings": warnings}
        else:
            task = service.draft_question(args.year, args.month, args.exam_set, args.section)
            result = (service.reference_material(args.year, args.month, args.exam_set,
                                                 args.section, task["task_text"])
                      if task else {"status": "missing"})
        print(json.dumps(result, ensure_ascii=False))
        return 0

    record = LearningRecord()
    if not record.path.exists():
        print(json.dumps({"status": "no_archive"}, ensure_ascii=False))
        return 0

    events, warnings = record.read()
    progress = summarize_learning(events)
    reviewed = {row["draft_id"] for row in events if row["kind"] == "feedback_ready"}

    def next_step(section: str, label: str) -> str:
        latest = next((row for row in reversed(events)
                       if row["kind"] == "draft_submitted" and row["section"] == section), None)
        if latest is None:
            return f"选择一套已收录的{label}题，提交一篇原稿。"
        if latest["draft_id"] in reviewed:
            return f"查看最近一篇{label}的评语，然后修改原稿。"
        return f"重试评阅最近一篇已保存的{label}原稿。"

    print(json.dumps({
        "status": "partial" if warnings else "ready",
        "writing_count": progress["writing_count"],
        "translation_count": progress["translation_count"],
        "writing_revisions": progress["writing_revisions"],
        "translation_revisions": progress["translation_revisions"],
        "next_writing_step": next_step("writing", "作文"),
        "next_translation_step": next_step("translation", "翻译"),
        "history_warnings": warnings,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
