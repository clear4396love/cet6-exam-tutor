"""Isolated writable, multi-turn Codex Skill evaluation for draft practice."""

import argparse
import json
import os
import re
import uuid
from pathlib import Path

from memory.learning_record import LearningRecord
from tools.cet6_skill_eval import (capture_trace, codex_executable, read_events,
                                   score_trace)


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "tmp" / "cet6-skill-multiturn"
FIRST_DRAFT = "The Beidou system are useful for many countries."
REVISED_DRAFT = "The Beidou system is useful for many countries."
WRITING_FIRST_DRAFT = (
    "Set realistic goals is important for students. When I was in high school, I try to "
    "finish all my tasks in one day, but I often feels tired and lose confident. Last year, "
    "I made a simple plan and worked on one goal at a time. It help me use my time better, "
    "and I become more patience. Now I believe that a clear goal give people direction, "
    "while persistent effort make it possible to improve step by step."
)
WRITING_REVISED_DRAFT = (
    "Setting realistic goals is important for students. When I was in high school, I tried "
    "to finish all my tasks in one day, but I often felt tired and lost confidence. Last "
    "year, I made a simple plan and worked on one goal at a time. It helped me use my time "
    "better, and I became more patient. Now I believe that a clear goal gives people "
    "direction, while persistent effort makes it possible to improve step by step."
)
SECTION_DRAFTS = {
    "translation": (FIRST_DRAFT, REVISED_DRAFT),
    "writing": (WRITING_FIRST_DRAFT, WRITING_REVISED_DRAFT),
}
_WRITING_LANGUAGE_FEEDBACK_TERMS = (
    "语法", "时态", "过去时", "过去时间", "用词", "词性", "连贯", "搭配",
    "主谓一致", "词形", "动词形式", "过渡", "句式", "拼写", "单复数",
)
_WRITING_SCOPE_VIOLATION = re.compile(
    r"(?:\d{1,3}\s*(?:分|/\s*100)|(?:预估|预计|预测|建议)\s*(?:得分|分数|评分)|"
    r"(?:中等偏[上下]|优秀|良好|较差|一般|偏高|偏低)(?:水平|等级|档次)|"
    r"(?:达到|满足|符合|接近|低于|高于).{0,18}(?:六级|CET[- ]?6|作文|写作).{0,18}"
    r"(?:要求|标准|水平|档次|等级)|"
    r"跑题|不切题|符合题意|不符合题意)"
)


def build_command(prompt: str, archive: Path, thread_id: str | None = None,
                  network_access: bool = False) -> list[str]:
    """Build a Codex turn with the same isolated archive in fresh and resumed chats."""
    configs = [
        "-c", "shell_environment_policy.set.LANGSMITH_TRACING=\"false\"",
        "-c", "shell_environment_policy.set.LANGCHAIN_TRACING_V2=\"false\"",
        "-c", "shell_environment_policy.set.EXAM_TUTOR_LEARNING_PATH="
        + json.dumps(archive.as_posix()),
        "-c", "shell_environment_policy.set.TEMP=" + json.dumps(archive.parent.as_posix()),
        "-c", "shell_environment_policy.set.TMP=" + json.dumps(archive.parent.as_posix()),
    ]
    if network_access:
        configs += ["-c", "sandbox_workspace_write.network_access=true"]
    if thread_id:
        return ([codex_executable(), "exec", "resume", "--json", "-c", 'sandbox_mode="workspace-write"']
                + configs + [thread_id, prompt])
    return ([codex_executable(), "exec", "--json", "--sandbox", "workspace-write"]
            + configs + ["-C", str(ROOT), prompt])


def run_turn(prompt: str, archive: Path, trace: Path, thread_id: str | None = None,
             network_access: bool = False, timeout: float = 240) -> dict:
    """Capture one real Codex turn without giving the agent the real archive path."""
    env = {**os.environ, "EXAM_TUTOR_LEARNING_PATH": str(archive),
           "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
           "TEMP": str(archive.parent), "TMP": str(archive.parent)}
    exit_code = capture_trace(build_command(prompt, archive, thread_id, network_access),
                              trace, env, timeout)
    events = read_events(trace)
    return {"exit_code": exit_code, "thread_id": thread_id_from_events(events),
            "completed": exit_code == 0 and any(event.get("type") == "turn.completed"
                                                for event in events), "events": events}


def thread_id_from_events(events: list[dict]) -> str | None:
    return next((event["thread_id"] for event in events
                 if event.get("type") == "thread.started"
                 and isinstance(event.get("thread_id"), str)), None)


def score_drafts(archive: Path, first_text: str, revised_text: str,
                 section: str = "translation") -> list[str]:
    """Require exactly two original submissions with an exact-text parent link."""
    rows, warnings = LearningRecord(archive).read()
    drafts = [row for row in rows if row["kind"] == "draft_submitted"
              and row["section"] == section]
    failed = []
    if not archive.exists():
        failed.append("archive_missing")
    if warnings:
        failed.append("archive_warning")
    if len(drafts) != 2:
        failed.append("draft_count")
    if len(drafts) >= 1 and drafts[0]["draft_text"] != first_text:
        failed.append("first_text")
    expected_scope = "language_only" if section == "writing" else "full"
    if any(row["review_scope"] != expected_scope for row in drafts):
        failed.append("review_scope")
    if len(drafts) >= 2:
        if drafts[1]["draft_text"] != revised_text:
            failed.append("revised_text")
        if drafts[1]["revision_of"] != drafts[0]["draft_id"]:
            failed.append("revision_parent")
    return failed


def run_flow(run_dir: Path, section: str = "translation") -> dict:
    """Exercise one real submission, same-chat revision, and fresh-chat reads."""
    if section not in SECTION_DRAFTS:
        raise ValueError("section must be writing or translation")
    first_text, revised_text = SECTION_DRAFTS[section]
    label = "作文" if section == "writing" else "翻译"
    root = RUN_ROOT.resolve()
    target = run_dir.resolve()
    if target == root or root not in target.parents:
        raise ValueError("run directory must be inside the isolated evaluation root")
    target.mkdir(parents=True, exist_ok=False)
    archive = target / "learning_events.jsonl"
    failed = []

    first = run_turn(
        f"$cet6-tutor 请保存并评阅我对2024年12月第1套{label}题的原稿。"
        + ("题目要求未完整核实，请只评语法、时态、用词、搭配和连贯性，不评价任务合规，也不估分。"
           if section == "writing" else "不要展示参考译文。")
        + "原稿如下：\n" + first_text,
        archive, target / "submit.jsonl")
    rows, warnings = LearningRecord(archive).read()
    drafts = [row for row in rows if row["kind"] == "draft_submitted"]
    if not first["completed"] or not first["thread_id"]:
        return {"status": "stopped", "reason": "submit_turn_incomplete", "run_dir": str(target),
                "exit_code": first["exit_code"], "trace": str(target / "submit.jsonl")}
    if (warnings or len(drafts) != 1 or drafts[0]["draft_text"] != first_text
            or drafts[0]["section"] != section
            or drafts[0]["review_scope"] != ("language_only" if section == "writing" else "full")):
        return {"status": "stopped", "reason": "first_draft_not_saved", "run_dir": str(target)}
    first_id = drafts[0]["draft_id"]
    failed += ["submit:" + error for error in score_trace({
        "command": f"tools.cet6_skill submit 2024 12 1 {section}",
        "forbid_command": ["tools.cet6_skill reference"],
        "reply_contains": [first_id],
    }, first["events"])]
    print("submit: saved", flush=True)

    revised = run_turn(
        f"$cet6-tutor 请把刚才那版{label}作为父稿，保存并评阅我的修改稿。"
        + ("只评语言，不评价任务合规或估分。" if section == "writing" else "不要展示参考译文。")
        + "修改稿如下：\n" + revised_text,
        archive, target / "revision.jsonl", thread_id=first["thread_id"])
    if not revised["completed"]:
        return {"status": "stopped", "reason": "revision_turn_incomplete", "run_dir": str(target),
                "exit_code": revised["exit_code"], "trace": str(target / "revision.jsonl"),
                "failed": failed}
    archive_failures = score_drafts(archive, first_text, revised_text, section)
    if archive_failures:
        return {"status": "stopped", "reason": "revision_not_saved", "run_dir": str(target),
                "failed": failed + archive_failures}
    rows, _ = LearningRecord(archive).read()
    revised_id = next(row["draft_id"] for row in rows
                      if row["kind"] == "draft_submitted" and row["revision_of"] == first_id)
    failed += ["revision:" + error for error in score_trace({
        "command": f"tools.cet6_skill submit 2024 12 1 {section}",
        "command_contains": ["--revision-of", first_id],
        "forbid_command": ["tools.cet6_skill reference"],
        "reply_contains": [revised_id],
    }, revised["events"])]
    print("revision: linked", flush=True)

    history = run_turn(
        f"$cet6-tutor 请查看本机保存的{label}原稿历史，给出两版原稿全文、版本ID和修改关系。",
        archive, target / "history-new-chat.jsonl")
    failed += ["history:" + error for error in score_trace({
        "command": f"tools.cet6_skill history --section {section}",
        "reply_contains": [first_text, revised_text, first_id, revised_id],
    }, history["events"])]
    print("history: checked", flush=True)

    progress = run_turn(
        "$cet6-tutor 查看本机作文与翻译学习进度，不要展示原稿。",
        archive, target / "progress-new-chat.jsonl")
    failed += ["progress:" + error for error in score_trace({
        "command": "tools.cet6_skill progress",
        "forbid_command": ["tools.cet6_skill history"],
        "reply_forbids": [first_text, revised_text],
        "allow_recovered_actions": ["progress"],
    }, progress["events"])]
    failed += ["archive:" + error for error in score_drafts(archive, first_text, revised_text, section)]
    print("progress: checked", flush=True)
    return {"status": "passed" if not failed else "failed", "failed": failed,
            "run_dir": str(target), "first_id": first_id, "revised_id": revised_id}


def retry_progress(run_dir: Path, section: str = "translation") -> dict:
    """Retry only a fresh-chat progress reply after an external interruption."""
    root = RUN_ROOT.resolve()
    target = run_dir.resolve()
    if target == root or root not in target.parents:
        raise ValueError("run directory must be inside the isolated evaluation root")
    archive = target / "learning_events.jsonl"
    first_text, revised_text = SECTION_DRAFTS[section]
    failed = score_drafts(archive, first_text, revised_text, section)
    if failed:
        return {"status": "stopped", "failed": failed, "run_dir": str(target)}
    trace = target / f"progress-retry-{uuid.uuid4().hex[:8]}.jsonl"
    result = run_turn("$cet6-tutor 查看本机作文与翻译学习进度，不要展示原稿。",
                      archive, trace)
    failed = score_trace({
        "command": "tools.cet6_skill progress",
        "forbid_command": ["tools.cet6_skill history"],
        "reply_forbids": [first_text, revised_text],
        "allow_recovered_actions": ["progress"],
    }, result["events"])
    return {"status": "passed" if not failed else "failed", "failed": failed,
            "run_dir": str(target), "trace": str(trace)}


def retry_review(run_dir: Path, draft_id: str, section: str = "translation") -> dict:
    """Retry feedback for one saved synthetic draft with sandbox network enabled."""
    root = RUN_ROOT.resolve()
    target = run_dir.resolve()
    if target == root or root not in target.parents:
        raise ValueError("run directory must be inside the isolated evaluation root")
    archive = target / "learning_events.jsonl"
    rows, warnings = LearningRecord(archive).read()
    drafts = [row for row in rows if row["kind"] == "draft_submitted"
              and row["section"] == section]
    first_text, revised_text = SECTION_DRAFTS[section]
    if (warnings or len(drafts) != 2 or draft_id not in {row["draft_id"] for row in drafts}
            or score_drafts(archive, first_text, revised_text, section)):
        return {"status": "stopped", "reason": "draft_not_verified", "run_dir": str(target)}
    trace = target / f"review-retry-{uuid.uuid4().hex[:8]}.jsonl"
    result = run_turn(
        f"$cet6-tutor 请重试评阅已保存的{('作文' if section == 'writing' else '翻译')}稿件，编号 {draft_id}。"
        + ("只评语言，不评价任务合规或估分。" if section == "writing" else "不要重复提交原稿，也不要展示参考译文。"),
        archive, trace, network_access=True)
    failed = score_trace({
        "command": f"tools.cet6_skill review {draft_id}",
        "forbid_command": ["tools.cet6_skill submit", "tools.cet6_skill reference"],
    }, result["events"])
    after, warnings = LearningRecord(archive).read()
    if warnings or len([row for row in after if row["kind"] == "draft_submitted"
                        and row["section"] == section]) != 2:
        failed.append("drafts_changed")
    if not any(row["kind"] == "feedback_ready" and row["draft_id"] == draft_id
               for row in after):
        failed.append("feedback_not_saved")
    return {"status": "passed" if not failed else "failed", "failed": failed,
            "run_dir": str(target), "trace": str(trace)}


def reviewed_history(run_dir: Path, section: str = "translation") -> dict:
    """Verify a new chat can recover both drafts and their persisted feedback."""
    root = RUN_ROOT.resolve()
    target = run_dir.resolve()
    if target == root or root not in target.parents:
        raise ValueError("run directory must be inside the isolated evaluation root")
    archive = target / "learning_events.jsonl"
    rows, warnings = LearningRecord(archive).read()
    drafts = [row for row in rows if row["kind"] == "draft_submitted"
              and row["section"] == section]
    first_text, revised_text = SECTION_DRAFTS[section]
    reviewed_ids = {row["draft_id"] for row in rows if row["kind"] == "feedback_ready"}
    if (warnings or score_drafts(archive, first_text, revised_text, section)
            or any(row["draft_id"] not in reviewed_ids for row in drafts)):
        return {"status": "stopped", "reason": "feedback_not_saved", "run_dir": str(target)}
    trace = target / f"reviewed-history-{uuid.uuid4().hex[:8]}.jsonl"
    result = run_turn(
        f"$cet6-tutor 请在新对话查看本机{('作文' if section == 'writing' else '翻译')}原稿历史，"
        "展示两版全文和版本ID，并分别说明已保存评语的要点，不要编造缺失内容。"
        + ("评语只检查语言，不要给分或评价是否切题。" if section == "writing" else ""),
        archive, trace)
    failed = score_trace({
        "command": f"tools.cet6_skill history --section {section}",
        "reply_contains": [first_text, revised_text, drafts[0]["draft_id"], drafts[1]["draft_id"]],
    }, result["events"])
    if section == "writing":
        reply = "\n".join(event.get("item", {}).get("text", "") for event in result["events"]
                          if event.get("type") == "item.completed"
                          and event.get("item", {}).get("type") == "agent_message")
        if not any(word in reply for word in _WRITING_LANGUAGE_FEEDBACK_TERMS):
            failed.append("language_feedback_missing")
        saved_feedback = [row["feedback"] for row in rows
                          if row["kind"] == "feedback_ready"
                          and row["draft_id"] in {draft["draft_id"] for draft in drafts}]
        if _WRITING_SCOPE_VIOLATION.search(reply + json.dumps(saved_feedback, ensure_ascii=False)):
            failed.append("writing_scope_violation")
    failed += ["archive:" + error for error in score_drafts(archive, first_text, revised_text, section)]
    return {"status": "passed" if not failed else "failed", "failed": failed,
            "run_dir": str(target), "trace": str(trace)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Writable multi-turn CET-6 Skill evaluation")
    parser.add_argument("--run-dir", type=Path, default=RUN_ROOT / uuid.uuid4().hex)
    parser.add_argument("--retry-progress", type=Path,
                        help="retry only the fresh-chat progress turn for an existing isolated run")
    parser.add_argument("--retry-review", type=Path,
                        help="retry feedback for one verified synthetic draft with sandbox network")
    parser.add_argument("--reviewed-history", type=Path,
                        help="fresh-chat read of both saved drafts and feedback")
    parser.add_argument("--draft-id", help="saved draft id for --retry-review")
    parser.add_argument("--section", choices=("writing", "translation"), default="translation",
                        help="section to exercise for a new flow or a retry")
    args = parser.parse_args(argv)
    if args.reviewed_history:
        report = reviewed_history(args.reviewed_history, args.section)
    elif args.retry_review:
        if not args.draft_id:
            parser.error("--draft-id is required with --retry-review")
        report = retry_review(args.retry_review, args.draft_id, args.section)
    else:
        report = (retry_progress(args.retry_progress, args.section) if args.retry_progress
                  else run_flow(args.run_dir, args.section))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
