# Task Plan: Repo-scoped CET-6 Codex Skill

## Goal

Expose the existing deterministic CET-6 tutor to Codex chats as one repo-scoped skill, without MCP or another chat-memory system. V1 supports cached-paper Q&A and read-only local writing/translation progress.

## Phases

1. [complete] Inspect existing service, learning record, Skill discovery, and execution environment.
2. [complete] Add failing checks for the small CLI contract and Skill discovery rules.
3. [complete] Add the Skill and minimal CLI adapter, preserving current fact sources.
4. [complete] Validate metadata, run focused and full tests, and report any environment limits.

## Boundaries

- Keep Streamlit, KEYS grading, caches, and existing local learning record unchanged.
- No MCP, new chat archive, user account binding, or draft submission in this Skill version.
- Do not claim a test passed unless it ran in this environment.

## Errors

- Existing project and parent `.venv` launchers point to Python installations unavailable in the sandbox; check an authorized runtime before test claims.
- `uv python list --only-installed` initially failed to initialize its default cache; reran with a workspace-local cache and found no installed interpreter.
- Existing WindowsApps Python can import dependencies from this repo's `.venv/Lib/site-packages` when `PYTHONPATH` is set for the command. Focused test was red (`No module named tools.cet6_skill`) then green (2 passed).
- Skill validator initially failed under Windows GBK locale while reading Chinese frontmatter. Setting `PYTHONUTF8=1` made validation pass without modifying the validator or Skill encoding.
- Focused reviewer-fix run initially failed one overly specific text assertion (`查看评语` versus `查看最近一篇作文的评语`); changed the test to assert the actual semantic contract (`评语` and `修改原稿`). Seven focused tests now pass.

## Final Verification

- Bundled `quick_validate.py`: `Skill is valid!`
- Full `pytest -q tests`: 183 passed, 1 existing `langchain-community` deprecation warning.
- Independent re-review: no remaining Critical or Important issues in the cached-only and privacy fixes.
- Live Codex host auto-discovery in a newly opened chat has not been exercised in this turn; user should test it with `$cet6-tutor` in this project folder.
