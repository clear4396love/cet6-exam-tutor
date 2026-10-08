# CET-6 单会话练习闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有答疑之外新增段落匹配逐题练习：学生提交后由 KEYS 确定性判分，记录当前会话作答并给出与证据量相称的解析和下一步建议。

**Architecture:** 用纯函数构造不含答案的练习视图、判分和统计；Service 将提交写入现有 Episode 轨迹；Streamlit 以显式控件驱动单题循环。判分和学习档位由代码决定，再把已判分结果、对应证据及会话统计交给 LLM 做一次普通反馈生成。DeepSeek 工具调用仅作独立探针，不进入首版练习链路。

**Tech Stack:** Python、现有 LangChain/DeepSeek 调用、Streamlit、JSONL Episode、pytest、现有场景评测 harness；不新增依赖或数据库。

**Spec:** `docs/superpowers/specs/2026-10-03-cet6-session-practice-design.md`

## Global Constraints

- 首版仅覆盖段落匹配（36–45 题），练习答案由 A–R 控件逐题提交。
- 判分只认缓存 KEYS；模型不参与答案比较，不得在提交前读取答案。
- 作答事件使用独立字段，不复用 `answer_mentioned` 或 `answer_agrees`。
- 统计函数只接受作答事件序列，不接收文件路径；学习记录仅限当前 Streamlit 会话。
- 少于 3 次作答为 `plan_insufficient_data`；3–7 次为 `weakness_snapshot`；达到 8 次为 `session_review`，不生成完整复习计划。
- “我不会”只触发鼓励和再次尝试，不判分、不增加作答次数、不泄露答案。
- 练习出题与提交不修改普通问答的 `LocationTable`；刷新或重新打开页面后，本次练习进度不恢复，界面须提示。
- 现有直接问答、段落匹配、仔细阅读、选词填空和翻译路径保持不变。
- 不新增 MCP、数据库、跨会话档案、自然语言作答识别、批量提交或自动练习推荐。

## Review Focus

- 题目缓存缺失、题干损坏或 KEYS 缺失：练习界面不给出可泄漏答案的回退内容，归 Task 1/2 测试。
- 小写、空白、非 A–R 或空提交：规范化/拒绝行为明确，不产生错误判分，归 Task 1/2 测试。
- 用户按“我不会”或重复练同一道题：前者不记 attempt，后者追加独立 attempt，归 Task 2/4 测试。
- 提交前的安全视图不得含答案；提交后才构造含 KEYS 的解析证据，归 Task 1/3 测试。
- LLM 调用异常或返回空文本：保留代码判分结果并按代码档位给固定建议，不影响普通问答，归 Task 3/4 测试。
- 练习出题或提交后继续聊天追问：普通问答的定位表保持原值，归 Task 2 测试。

---

### 独立实验：验证 DeepSeek 工具调用能力（不阻塞首版）

**Files:**
- Create temporarily: `tmp/probe_deepseek_tool_call.py`（运行后删除，不提交）

**Interfaces:**
- Consumes: 当前 `.venv` 中安装的 LangChain 版本、现有 `DEEPSEEK_API_KEY`、模型名 `deepseek-v4-flash`。
- Produces: 默认思考模式与关闭思考模式下是否支持原生 `tool_choice` 的记录，供后续 Agent 功能设计参考；不改变首版实现路径。

- [ ] **Step 1: 用一个无副作用的 `echo(value: str) -> str` 假工具写一次性探针**

使用当前 LangChain 的 `bind_tools([echo], tool_choice="echo")` 分别在默认思考模式、`extra_body={"thinking": {"type": "disabled"}}` 下各发一次简单请求；只打印 tool-call 名称/参数，不打印环境变量或密钥。不得访问真题答案或写入缓存。

- [ ] **Step 2: 运行探针并记录结论**

Run: `..\.venv\Scripts\python.exe tmp\probe_deepseek_tool_call.py`（从 `exam-tutor` 目录运行；若当前虚拟环境不可用，待环境恢复后再做，不阻塞首版）
Expected: 至少确认原生 tool call 在哪种配置下可用；若两种都不通，记录为“不支持”，不要反复重试或扩大实验。

- [ ] **Step 3: 删除临时探针**

Run: `Remove-Item -LiteralPath tmp\probe_deepseek_tool_call.py`
不将探针、API 输出或密钥加入仓库；只在计划或实验记录中写结论，不把探针结果作为首版功能的前置条件。

---

### Task 1: 安全练习视图、确定性判分与纯统计

**Files:**
- Create: `retrieval/practice.py`
- Create: `tests/test_practice.py`
- Reuse: `retrieval/structured.py` 的 `get_question`、`get_paragraphs`、`get_answer`、`clean_text`

**Interfaces:**
- Produces: `get_practice_item(paper: dict, question_number: int) -> dict | None`，仅返回 `{"question_number": int, "stem": str, "paragraphs": dict[str, str]}`。
- Produces: `grade_attempt(paper: dict, question_number: int, submitted_answer: str) -> dict | None`，返回 `{"submitted": str, "answer": str, "correct": bool}`；无可验证 KEY 或非法答案时返回 `None`。
- Produces: `summarize_attempts(events: Sequence[Mapping[str, object]]) -> dict`，输出 `attempt_count`、`correct_count`、0–1 范围的 `accuracy`/`recent_accuracy`、`by_range`、`repeated_misses` 和 `tier`。

- [ ] **Step 1: 为练习视图和判分写失败测试**

增加 `test_practice_item_omits_answer_and_answer_segment`、`test_grade_attempt_uses_keys_and_normalizes_letter`、`test_grade_attempt_rejects_invalid_answer_or_missing_key`。断言视图没有 `answer`/KEYS，也没有把正确段落标记混入展示字段；判分只比对缓存答案。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_practice.py -q`
Expected: 新模块或函数缺失导致 FAIL。

- [ ] **Step 3: 实现最小安全视图和判分函数**

在 `retrieval/practice.py` 中仅组合现有结构化读取函数；把提交答案去首尾空白并转大写，只接受 A–R。不要返回原始缓存对象。

- [ ] **Step 4: 为纯统计和三级门槛写失败测试**

增加 `test_summarize_attempts_ignores_non_attempt_rows`、`test_summarize_attempts_calculates_ranges_and_repeated_misses`、`test_practice_tier_boundaries`。最近正确率按最近最多 5 次作答计算；重复错题指同一题至少答错 2 次。

- [ ] **Step 5: 运行统计测试确认失败**

Run: `python -m pytest tests/test_practice.py -q`
Expected: 三个新增统计测试 FAIL。

- [ ] **Step 6: 实现纯统计函数**

阈值精确为 0–2=`plan_insufficient_data`、3–7=`weakness_snapshot`、8+=`session_review`；统计总正确率、最近最多 5 次正确率、36–40 与 41–45 区间及重复错题，不统计模型生成的陷阱标签。函数只接受事件序列。

- [ ] **Step 7: 运行全测试并提交**

Run: `python -m pytest tests/test_practice.py -q`
Expected: PASS；所有题目展示、KEYS 判分和统计边界均由纯函数测试覆盖。

---

### Task 2: Episode 作答事件与 Service 接口

**Files:**
- Modify: `memory/episode.py`
- Modify: `retrieval/service.py`
- Modify: `tests/test_state_and_trace.py`
- Create or extend: `tests/test_practice.py`

**Interfaces:**
- Produces: `Service.practice_question(year: int, month: int, exam_set: int, question_number: int) -> dict | None`。
- Produces: `Service.submit_practice_answer(year: int, month: int, exam_set: int, question_number: int, submitted_answer: str) -> dict | None`；成功结果含 `submitted`、`answer`、`correct`、`trace_id`，并追加一条 Episode。
- Produces: `Service.practice_progress() -> dict`；内部读取当前 Episode，再将仅含 attempt 的事件序列传给 `summarize_attempts`。
- Episode 新增固定字段 `attempt_answer`、`attempt_correct`；作答行的 `stage` 为 `attempt_correct` 或 `attempt_wrong`，`filters` 写入试卷定位和题号，供提交后反馈按 trace 重新读取证据。

- [ ] **Step 1: 写 Episode schema 与 Service 行为测试**

断言普通问答的 `answer_agrees` 保持原语义；attempt 使用独立字段；缺缓存/缺 KEY/非法输入不写作答事件；重复提交同题产生两条 attempt；普通问答行被统计器忽略。先完成一次聊天定位，再分别调用 `practice_question` 和 `submit_practice_answer`，断言 `LocationTable.to_dict()` 前后相同，并验证随后的普通追问仍指向原题。

- [ ] **Step 2: 运行相关测试确认失败**

Run: `python -m pytest tests/test_state_and_trace.py tests/test_practice.py -q`
Expected: 缺少 attempt 字段/API 的新测试 FAIL，既有测试保持可收集。

- [ ] **Step 3: 扩展固定 Episode schema 并实现 Service 桥接**

在 `memory/episode.py` 为 attempt 字段设 `None` 默认值，并把 `stage` 注释由 18 个值更新为 20 个。`Service.practice_question` 只读缓存且不改普通定位表；`submit_practice_answer` 调用 Task 1 判分函数并追加含完整 `filters` 的事件，同样不改定位表；`practice_progress` 只传事件列表给纯统计函数。“我不会”不是提交，Service 不记录 attempt。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_state_and_trace.py tests/test_practice.py -q`
Expected: PASS；现有轨迹 schema、状态机断言和新 attempt 事件均通过。

---

### Task 3: 一次反馈生成与降级

**Files:**
- Modify: `retrieval/answer_prompt.py`
- Modify: `retrieval/generation.py`
- Modify: `retrieval/service.py`
- Extend: `tests/test_practice.py`

**Interfaces:**
- Produces: `AnswerGeneration.generate_practice_feedback(evidence: str, result: dict, progress: dict) -> str`；复用现有模型配置，仅调用一次模型，不绑定工具。
- Produces: `Service.practice_feedback(attempt_trace_id: str) -> str`；仅从本会话已完成的作答行读取题目定位与判分事实，调用 `build_evidence` 获取提交后证据及 `practice_progress()` 获取代码统计。
- 反馈失败时由 Service 按 `tier` 返回对应的固定短建议；判分结果和标准答案继续由 `submit_practice_answer` 的代码结果独立提供。

- [ ] **Step 1: 用假模型写反馈边界和降级测试**

验证只有成功提交后的 trace 能触发一次模型调用；传入模型的事实来自该行判分、`build_evidence` 和代码统计；未知 trace 返回安全提示，模型异常或空文本按 `tier` 返回固定短建议，其中 0–2 次必须说明记录不足；这些情况不会改写已记录的 `attempt_correct`、`answer_keys` 或作答次数。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_practice.py -q`
Expected: 新反馈接口或 prompt 缺失导致 FAIL。

- [ ] **Step 3: 实现一次反馈生成**

在 `answer_prompt.py` 增加练习反馈 prompt：解释本题证据、说明当前档位允许的统计事实、只给一条下一步建议；0–2 次作答时明确记录不足，8 次及以上只做本会话复盘。`Service.practice_feedback` 依据 trace 从当前 Episode 取记录，用该行 `filters` 读缓存，并在提交后调用 `build_evidence(paper, question_number, attempt_answer)`；将记录中的判分事实、证据与 `practice_progress()` 交给 `AnswerGeneration.generate_practice_feedback`。模型结果仅作辅助文字，空文本/异常时按代码 `tier` 返回固定短建议。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_practice.py -q`
Expected: PASS；模型调用一次，失败时保留代码判分且按档位返回固定短建议。

---

### Task 4: Streamlit 逐题练习交互

**Files:**
- Modify: `streamlit_app.py`
- Modify: `tests/test_streamlit_app.py`

**Interfaces:**
- Uses Task 2 `Service.practice_question`、`Service.submit_practice_answer`、`Service.practice_progress` and Task 3 `Service.practice_feedback`.
- Keeps existing chat input and message rendering unchanged for ordinary Q&A.

- [ ] **Step 1: 为练习面板写 AppTest**

增加测试：一次仅展示一道段落匹配题；A–R 显式控件单题提交一次并先显示代码判分；提交前页面状态不含答案；“我不会，鼓励我试试”保留当前题、显示鼓励且不调用 submit；下一题开始后仍能看到本会话累计统计；界面提示刷新后进度不恢复；不出现 10 题批量提交控件。

- [ ] **Step 2: 运行 UI 测试确认失败**

Run: `python -m pytest tests/test_streamlit_app.py -q`
Expected: 现有聊天测试通过，新练习交互测试因控件/Service 方法缺失失败。

- [ ] **Step 3: 实现独立练习区**

用独立表单输入年份、月份、套数和 36–45 题号，点击“出题”后仅缓存 Task 1 的安全视图到 `st.session_state`；无数据时显示明确提示且不显示答案。用单题 A–R 选择控件提交。提供“我不会，鼓励我试试”按钮，固定文案鼓励再次尝试但不判分、不记次数。提交后先独立展示代码判分和会话统计，再用 Task 3 的一次反馈调用展示解析/建议；模型失败时判分仍可见并显示对应档位的固定短建议。提示刷新或重新打开页面后本次进度不恢复。完成后允许选择下一题；普通聊天继续走原 `Service.process`。

- [ ] **Step 4: 运行 UI 测试并提交**

Run: `python -m pytest tests/test_streamlit_app.py -q`
Expected: PASS；现有聊天界面断言与新增逐题交互断言均通过。

---

### Task 5: 评测覆盖与全量回归

**Files:**
- Modify: `tools/scenario_eval.py`
- Modify: `tests/test_scenario_eval.py`
- Modify as needed: `tests/test_practice.py`, `tests/test_streamlit_app.py`

**Interfaces:**
- Extends existing scenario harness; does not add a second evaluator or overwrite existing scenarios during tests.
- Practice scenarios compare deterministic expected fields: stage, submitted answer, KEYS, correctness, attempt count, tier and fallback result.

- [ ] **Step 1: 加入本地可复现的练习场景测试**

在 `tests/test_scenario_eval.py` 测试 `PRACTICE_CASES`、新增 `score_practice_step(expect, actual) -> list[str]` 和 `--practice` 选择行为。覆盖正确/错误提交、缺 KEY、我不会不计数、同题重复练习、三级阈值及模型失败保留判分；使用假模型/离线缓存，不发真实 API 请求。

- [ ] **Step 2: 运行新场景测试确认失败**

Run: `python -m pytest tests/test_scenario_eval.py tests/test_practice.py tests/test_streamlit_app.py -q`
Expected: 新的 `PRACTICE_CASES` / `score_practice_step` 相关测试 FAIL。

- [ ] **Step 3: 实现同一 harness 内的离线练习场景**

在 `tools/scenario_eval.py` 添加单独的 `PRACTICE_CASES`、`score_practice_step()` 和 `--practice` 运行开关；复用现有 `--only` 选择场景。不得更改既有 `CASES` 的 ID、期望或默认运行行为；练习场景只使用离线缓存及假模型。

- [ ] **Step 4: 运行场景与功能测试确认通过**

Run: `python -m pytest tests/test_scenario_eval.py tests/test_practice.py tests/test_streamlit_app.py -q`
Expected: PASS；测试中的错误预期与实际不匹配时 `score_practice_step` 返回具体失败字段。

- [ ] **Step 5: 运行全量测试与评测入口检查**

Run: `python -m pytest -q`
Expected: 所有现有和新增测试 PASS；`tools/scenario_eval.py` 的原有场景 ID/期望不变，新增练习场景单独可选运行。

- [ ] **Step 6: 检查最终 diff 并提交**

只暂存本功能涉及的文件；确认 `.env`、episodes 数据、缓存 JSON 与 OCR 临时目录均未进入 diff。提交信息建议：`feat: add session-scoped practice loop`。

---

## Final Verification

- Run: `python -m pytest -q`
- Run: `streamlit run streamlit_app.py`，手动完成 8 道段落匹配练习并检查三档反馈与“我不会”行为。
- Run: `python tools/scenario_eval.py --practice --only 1`；确认只输出第 1 个练习场景，不覆盖既有结果文件。
- Inspect: `git diff --check` and `git status --short`；确认无缓存、API 密钥、会话轨迹或临时 OCR 文件混入。
