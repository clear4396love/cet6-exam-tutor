# Findings

- Official OpenAI documentation says Codex discovers repo skills in `.agents/skills` from CWD to repository root; `SKILL.md` requires `name` and `description`, while scripts are optional.
- `Service.process(user_message)` is the current Q&A entrypoint. It delegates semantic intent to DeepSeek but keeps paper location and KEYS-backed answer selection in code.
- `Service.learning_progress(preferred_section)` reads the local JSONL record and computes count/action data. The Skill should expose only writing/translation counts and actionable summaries for v1.
- `LearningRecord` defaults to `Path.home() / ".exam-tutor" / "learning_events.jsonl"`, overridable by `EXAM_TUTOR_LEARNING_PATH`.
- No existing Skill was found under this project's `.agents` directory. `retrieval/service.py` has only an interactive CLI; no single-shot command exists for Codex.
- The parent Git repository has many unrelated untracked files and staged changes. Preserve all of them; no broad staging/reset.
- A read-only fresh-agent baseline could manually find Q43 KEY=I and evidence in JSON, but it needed ad-hoc repository exploration and could not safely claim private progress. The Skill's value is a scoped, repeatable entrypoint and output contract, not new answer logic.
- With escalation, WindowsApps Python plus this repo's `.venv/Lib/site-packages` imports pytest and Streamlit without installing anything. Both `.venv` launchers remain unusable in this sandbox.
- Independent review found that `summarize_learning.next_action` can include free-form `feedback.priority`, potentially quoting draft text. The Skill CLI now constructs fixed writing/translation next steps from event facts only, while leaving existing UI summaries unchanged.
- Independent review also found the Section B Service path could parse PDF and write a cache on miss. The Skill CLI now requests `Service(cached_only=True)`, which selects the existing read-only loader only for that Service instance.
