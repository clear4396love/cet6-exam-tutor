"""Score real `codex exec --json` Skill traces against a small prompt set.

This is intentionally separate from Service/CLI tests: those cannot prove
that an agent chose the right tool or respected the reveal gate.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "cet6_skill_cases.json"


def codex_executable() -> str:
    """Resolve Windows npm .cmd shims before passing the CLI to CreateProcess."""
    return shutil.which("codex") or "codex"


def score_trace(case: dict, events: list[dict]) -> list[str]:
    """Return failed observable checks for one completed Codex run."""
    commands = [event["item"] for event in events
                if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "command_execution"]

    def skill_action(command: str) -> str | None:
        match = re.search(
            r"tools\.cet6_skill(?:\.py)?(?:\s+|['\"]\s*,\s*['\"])([a-z][a-z_-]*)",
            command,
        )
        return match.group(1) if match else None

    command_text = "\n".join(str(item.get("command", "")) for item in commands)
    messages = [event["item"].get("text", "") for event in events
                if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "agent_message"]
    reply = messages[-1] if messages else ""
    failed = []
    if not any(event.get("type") == "turn.completed" for event in events):
        failed.append("incomplete_trace")
    recoverable_actions = set(case.get("allow_recovered_actions", []))
    if any(
        "tools.cet6_skill" in str(item.get("command", ""))
        and item.get("exit_code") not in (None, 0)
        and not (
            (action := skill_action(str(item.get("command", "")))) in recoverable_actions
            and any(skill_action(str(later.get("command", ""))) == action
                    and later.get("exit_code") == 0
                    for later in commands[index + 1:])
        )
        for index, item in enumerate(commands)
    ):
        failed.append("tool_failed")
    if case.get("command") and case["command"] not in command_text:
        failed.append("missing_command")
    if any(token not in command_text for token in case.get("command_contains", [])):
        failed.append("wrong_coordinates")
    if case.get("no_skill_command") and "tools.cet6_skill" in command_text:
        failed.append("unexpected_skill_command")
    if any(token in command_text for token in case.get("forbid_command", [])):
        failed.append("forbidden_command")
    if any(token not in reply for token in case.get("reply_contains", [])):
        failed.append("reply_missing")
    if any(token in reply for token in case.get("reply_forbids", [])):
        failed.append("reply_leak")
    plain_reply = re.sub(r"[*_`]+", "", reply)
    if case.get("reply_pattern") and not re.search(case["reply_pattern"], plain_reply):
        failed.append("reply_pattern")
    return failed


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def capture_trace(command: list[str], path: Path, env: dict[str, str], timeout: float) -> int | None:
    """Write events as they arrive; return None after a bounded timeout."""
    with path.open("wb") as output:
        process = subprocess.Popen(command, env=env, cwd=ROOT,
                                   stdout=output, stderr=subprocess.DEVNULL)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CET-6 Codex Skill trace evaluation")
    parser.add_argument("--run", action="store_true", help="capture new Codex traces; otherwise score saved traces")
    parser.add_argument("--only", help="one case id")
    parser.add_argument("--trace-dir", type=Path, default=ROOT / "tmp" / "cet6-skill-eval")
    args = parser.parse_args(argv)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if args.only:
        cases = [case for case in cases if case["id"] == args.only]
        if not cases:
            parser.error(f"unknown case: {args.only}")
    args.trace_dir.mkdir(parents=True, exist_ok=True)
    passed = run = 0
    for case in cases:
        path = args.trace_dir / f"{case['id']}.jsonl"
        if args.run:
            with tempfile.TemporaryDirectory(prefix="cet6_skill_eval_") as private_dir:
                isolated_learning_path = Path(private_dir) / "learning_events.jsonl"
                env = {**os.environ,
                       "EXAM_TUTOR_LEARNING_PATH": str(isolated_learning_path),
                       "LANGSMITH_TRACING": "false",
                       "LANGCHAIN_TRACING_V2": "false"}
                command = [codex_executable(), "exec", "--json", "--ephemeral", "--sandbox", "read-only",
                           "-c", "shell_environment_policy.set.LANGSMITH_TRACING=\"false\"",
                           "-c", "shell_environment_policy.set.LANGCHAIN_TRACING_V2=\"false\"",
                           "-c", "shell_environment_policy.set.EXAM_TUTOR_LEARNING_PATH="
                                 + json.dumps(isolated_learning_path.as_posix()),
                           "-C", str(ROOT), case["prompt"]]
                try:
                    exit_code = capture_trace(command, path, env, timeout=180)
                except OSError as exc:
                    print(f"{case['id']}: RUN_ERROR {exc}")
                    continue
                else:
                    if exit_code is None:
                        print(f"{case['id']}: TIMEOUT; partial trace saved")
                    elif exit_code:
                        print(f"{case['id']}: Codex exit {exit_code}; inspect saved trace")
        if not path.exists():
            print(f"{case['id']}: NOT_RUN")
            continue
        try:
            failed = score_trace(case, read_events(path))
        except (OSError, ValueError, KeyError) as exc:
            failed = [f"trace_error:{exc}"]
        run += 1
        passed += not failed
        print(f"{case['id']}: {'PASS' if not failed else ', '.join(failed)}")
    print(f"Skill traces: {passed}/{run} passed; {len(cases) - run} not run")
    return 0 if passed == run and run == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
