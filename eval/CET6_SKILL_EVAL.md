# CET-6 Skill evaluation

`cet6_skill_cases.json` contains 12 fresh-chat, read-only Codex prompts. It covers
explicit/implicit reading lookup, a distractor explanation, missing coordinates,
writing/translation task views, the reference reveal gate, progress/history,
cache misses, and an unrelated negative control.

These scenarios require the 38 cached paper JSONs shipped with the repository.
A clean clone can run them after installing dependencies and configuring its own
model access where required. The historical counts below remain observations
from local runs, not claims that every clone will reproduce the same model output.

From the project root, with its `.venv` active:

```powershell
python -m pytest -q
python -m tools.cet6_skill_eval --run --only translation-task-hidden
python -m tools.cet6_skill_eval
```

`pytest.ini` limits discovery to `tests/` and places pytest's temporary files
under the Git-ignored `.pytest-tmp/`. On Windows, if the system Temp directory has
restricted permissions, set Python's temporary directory before starting it:

```powershell
$localTestTemp = (Resolve-Path .\tmp).Path
$env:TEMP = $localTestTemp
$env:TMP = $localTestTemp
python -m pytest -q
```

`--run` resolves the installed Codex launcher (including npm's Windows
`codex.cmd`) and starts `codex exec --json --ephemeral --sandbox read-only` in a fresh
chat per case and saves traces under `tmp/cet6-skill-eval/`. It redirects the
learning-record path to a temporary file through Codex's shell environment
configuration, and disables LangSmith tracing for the evaluated tool calls.
The trace is written as events arrive; a 180-second timeout retains its partial
trace and is reported as incomplete, not as a wrong answer. The `tmp/` directory
is local and Git-ignored because traces can contain private tool output.
Run one case at a time first: each case invokes a real agent and may use model
quota. Without `--run`, the command
scores saved traces and reports unrun cases separately. A nonzero exit means
some requested cases failed or were not run.

This trace score checks observable commands, coordinates, final-output markers,
the no-spoiler gate, and completed runs. It does **not** prove the quality of a
Chinese explanation. Draft submission, feedback failure/retry, and cross-chat
recovery are covered by the separate writable evaluation below.

## Observed run (2026-10-08)

All 12 saved fresh-chat traces passed the observable checks (`12/12`). One
Q48 explanation attempt was interrupted by Codex model capacity after its
project command had succeeded; a single retry completed and passed. The
evaluator was also adjusted, with a red/green regression test, to accept a
correct answer letter surrounded by Markdown emphasis (`**E**`). At that
earlier run, the project test suite passed `194` tests when `TEMP` and `TMP`
were set to the local `tmp` directory; the fresh full-suite result is recorded
in the revalidation section below.

This is an observed small-sample route/safety check, not a measured general
answer-accuracy rate. The run did not cover writable draft submission or
cross-chat recovery.

## Writable multi-turn draft evaluation

From the project root, run:

```powershell
python -m tools.cet6_skill_multiturn_eval
```

This creates a new ignored directory under `tmp/cet6-skill-multiturn/`. By
default, it uses two synthetic Beidou translation drafts. To evaluate an essay,
pass `--section writing`:

```powershell
python -m tools.cet6_skill_multiturn_eval --section writing
```

The writing scenario uses synthetic drafts with agreement, tense, and word-form
errors. It checks exact saved text, the linked revision, and that both records
carry `review_scope: language_only`; the fresh-chat history reply must discuss
language without estimating a score or judging task relevance. Each section
uses an isolated learning-record path under the run directory. The first two
turns share one Codex chat (submission and linked revision); history and
progress each use a fresh chat. The evaluator checks Skill commands, the
two-version history reply, and no draft text in the progress reply. It stops
before revision if the first draft was not saved. Raw traces stay local and
Git-ignored. Codex CLI session files may also persist because same-chat resume
cannot use `--ephemeral`.

If Codex capacity interrupts only the final progress turn, rerun it without
resubmitting either draft:

```powershell
python -m tools.cet6_skill_multiturn_eval --retry-progress tmp/cet6-skill-multiturn/RUN_ID
```

The default workspace-write sandbox may block the external DeepSeek review
call, leaving drafts saved with `pending` feedback. For an isolated synthetic
draft only, an explicit retry can enable outbound network for that one Codex
turn while retaining the workspace-write filesystem sandbox:

```powershell
python -m tools.cet6_skill_multiturn_eval --retry-review tmp/cet6-skill-multiturn/RUN_ID --draft-id DRAFT_ID
python -m tools.cet6_skill_multiturn_eval --reviewed-history tmp/cet6-skill-multiturn/RUN_ID
```

Add `--section writing` to either command when retrying the essay scenario.

Do not point these commands at private student drafts without understanding
that the configured model receives the submitted text. The writable eval does
not change global Codex network settings, cache answers, or the real local
learning record.

On 2026-10-08, the synthetic run saved two exact drafts with a correct parent
link. A new chat retrieved both drafts, and a progress-only chat did not read
history or reveal draft text. The first progress turn was interrupted by Codex
model capacity after its tool call and passed on one isolated retry. Initial
feedback was `pending` in the network-restricted sandbox; isolated retries
produced two persisted feedback events, and a new chat recovered both. Manual
review confirmed the first feedback identified `system are` as a subject–verb
agreement error, while the revised draft no longer received that error; both
feedback records identified the substantial omissions in the one-sentence
translation. This is one synthetic end-to-end path, not a general feedback
quality score or an essay-writing evaluation.

## Observed writing evaluation (2026-10-08)

The real Codex `--section writing` flow saved two exact synthetic essays, linked
the revision to its parent, restored both in a fresh chat, and kept the draft
text out of the progress reply. The first Codex attempt stopped at model
capacity before saving; a fresh isolated run completed. The essay task was
confirmed as `language_only` in both saved records.

The first real feedback check exposed a scope leak: the revised draft's
feedback described it as “中等偏下水平”. This was not a numeric score, but it
was still a grade-like label. The reviewer prompt now forbids such labels, the
service rejects estimated scores and proficiency bands before saving, and the
evaluator inspects persisted feedback as well as the fresh-chat summary. A
regression test confirms a stored grade label fails the writing scope check.

After that correction, the configured reviewer generated feedback for both
synthetic versions in a separate isolated archive. The first feedback called
out tense, agreement, and word-form errors; the revised feedback focused on
remaining collocation and coherence issues. A fresh Codex chat restored both
versions and those feedback summaries, and the scope check passed. This
rechecked the changed reviewer and history path; it is still one synthetic
essay case, not a general feedback-accuracy rate.

## Fresh writing revalidation (2026-10-08)

After the evaluator's recovered-action and language-feedback checks were fixed,
the complete `--section writing` flow was rerun in a new isolated directory:
`tmp/cet6-skill-multiturn/8dbc64314996429c814409599aae3c4b/`. Submission,
revision, fresh-chat history, and progress checks passed. The two synthetic
drafts were saved exactly, the second linked to the first, and progress showed
counts and next steps without exposing either draft.

As in the earlier run, both initial reviewer calls returned `pending` because
of `APIConnectionError`; no feedback was invented. Explicit `--retry-review`
calls for each synthetic draft then passed and persisted language-only
feedback. A fresh `--reviewed-history` check passed, recovering both drafts,
their relationship, and the stored feedback without a score or task-compliance
judgment. The feedback identified the first draft's agreement, tense, and
word-form errors; the revised draft's feedback focused on remaining word-choice
and collocation issues. Codex transport also needed to reconnect after request
timeouts, but the turns completed successfully.

The full automated suite was rerun with the project's `.venv` and an isolated
pytest temp directory: **217 passed**, with one existing
`langchain-community` deprecation warning. This remains one synthetic essay
scenario and validates the workflow/scope contracts, not general review
accuracy or real-student outcomes. All writable evaluation data is under the
Git-ignored `tmp/`; the user's local learning archive was not used.

## Launcher and feedback guard follow-up (2026-10-08)

An independent Windows check found that `subprocess` could not start the npm
`codex.cmd` shim from a bare `"codex"` command. Both evaluation tools now
resolve the executable through `PATH`. A regression test launches a real
temporary `.cmd` shim, and one new read-only Codex run of
`reference-asks-confirmation` completed with **1/1 passed**. The older 12 saved
traces still score **12/12**; this follow-up did not rerun all 12 with new
model calls.

The writing feedback validator now receives the saved `review_scope`. For
`language_only`, it requires an overall language observation and rejects
task-compliance claims. Writing feedback also rejects the tested level claim
“远未达到六级作文的基本要求”; the independent history evaluator flags it as well.
Verified full-scope writing can still discuss task relevance, and translation
keeps its existing full-scope behavior. These checks cover concrete observed
phrases; free-form model text cannot be exhaustively classified by regular
expressions alone.

After these changes, a clean local-temp run of `python -m pytest -q` reported
**224 passed**, with the existing `langchain-community` deprecation warning.
