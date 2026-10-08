# CET-6 本机学习闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让阅读作答跨会话恢复，并让学生提交作文、译文原稿，获得可追溯的 AI 参考评语、保留修改版本和一个下一步建议。

**Architecture:** 单个用户本地 JSONL 账本保存阅读作答、主观题原稿和反馈事件；现有 KEYS 判分与 `summarize_attempts()` 保持客观事实来源。新增纯函数提供安全题目与评语校验，`Service` 统一协调保存、评阅和进度；Streamlit 只负责显式输入和展示。

**Tech Stack:** Python 标准库、现有 LangChain/DeepSeek、Streamlit 1.61.1、pytest、现有 `tools/scenario_eval.py`；不新增数据库或依赖。

**Spec:** `docs/superpowers/specs/2026-10-05-cet6-local-learning-memory-design.md`

## Global Constraints

- 本机档案默认路径是 `Path.home() / ".exam-tutor" / "learning_events.jsonl"`；可用 `EXAM_TUTOR_LEARNING_PATH` 指定另一处可写的本机 JSONL 文件，`Service(learning_path=...)` 的显式参数优先于环境变量。绝不扫描或导入旧 `episodes/`。
- 只记录显式提交；阅读只认缓存 KEYS，作文/翻译只给“AI 参考评语，非官方阅卷”，不出预测分数，也不合并正确率。
- 作文/译文拒绝纯空白和超过 10,000 字符；原稿必须先写盘成功，才能发给 DeepSeek。失败或重试不能凭空增加提交次数。
- 反馈局部引文必须存在于学生原稿；翻译漏译项可引用缓存中文原文。模型输入只含当前题目和当前稿件，不含整份历史记录或账本路径。
- 练习出题、提交、评阅、进度查询均不改聊天 `LocationTable`；不新增 Skill、MCP、云同步或旧轨迹迁移。
- 当前父级 `.venv` 的 `python.exe` 存在，但启动时指向不存在的 WindowsApps Python；实施前先验证可工作的解释器，失败时停在环境前置检查，不把环境错误当作红灯测试，也不擅自重建用户环境。父目录是 Git 仓库，但 `HEAD` 尚无提交且工作区已有用户改动；命令需用单次 `git -c safe.directory=D:/vscode/python/ai_agent/langchain ...` 绕过沙箱账户的所有权误报。不得在本计划中擅自初始化历史或提交用户改动。

## Review Focus

- 两个浏览器标签页或一次按钮重跑触发同一稿重复提交/评阅：同一 `draft_id` 最多采用一条有效反馈；同一显式提交操作需有稳定幂等键，重试不得制造第二份原稿；Task 3/4/6 测试。
- 账本中夹有截断 JSON、无效 UTF-8、未知事件或非布尔 `attempt_correct`：跳过结构坏行并提示，不污染客观统计；Task 1/5 测试。本机账本不是防篡改存储，不声称能识别手工伪造的合法布尔值。最近一次以有效事件的追加顺序为准，不按可被修改的 `ts` 排序。
- 学生拿另一套卷的 `draft_id` 当 `revision_of`：拒绝跨卷/跨板块串版本；Task 3 测试。
- 学生稿件里写“忽略以上要求”，模型却返回不存在的引文：稿件按数据处理，失实问题丢弃；Task 4 测试。
- 作文要求仅按明确通过的白名单字段开放完整任务合规评阅；其他情况（包括 OCR 损坏、混入听力/阅读、图表资料缺失）统一 `language_only`，不推测“污染”来源。38 套缓存中 26 套无 `writing_directions`，12 套有；其中 3 套有 chart/graph 字样但缺可用图表材料，均不得 `full`；Task 3/6 测试。

---

### Task 1: 耐久学习账本

**Files:** Create `memory/learning_record.py`, `tests/conftest.py`; test `tests/test_learning_record.py`.

**Interfaces:** `LearningRecord(path: Path | None = None)`, `append(event: dict) -> dict`（生成 `event_id` 和带时区 `ts`，返回采用的事件行；写失败抛异常），`read() -> tuple[list[dict], list[str]]`（有效事件、可显示警告）。路径解析优先级：显式 `path` > `EXAM_TUTOR_LEARNING_PATH` > 用户目录默认文件；环境变量必须是明确的本机文件路径，不接受空值后静默改存项目目录。公共键为 `kind`、`event_id`、`ts`、`section`、`filters`；阅读另有 `stage`、`attempt_answer`、`attempt_correct`；原稿另有 `draft_id`、`draft_text`、`task_text`、`review_scope`、`revision_of`、`submission_id`（同一次提交操作的幂等键）；反馈另有 `draft_id`、`feedback`。`kind` 固定为 `reading_attempt`、`draft_submitted`、`feedback_ready`，`section` 固定为 `reading`/`writing`/`translation`，`filters` 含年/月/套，阅读另含题号。各 kind 的固定键白名单和字段类型在读写时校验；未知键（尤其 API Key、阅读标准答案）拒绝写入。`draft_submitted` 的 `draft_id` 等于本行 `event_id`。在同一应用进程内，账本层以共享锁串行化同一路径的“读取幂等键→追加”：`draft_submitted` 按 `submission_id`，`feedback_ready` 按 `draft_id` 去重；重复时返回已有行，跨进程并发不作首版承诺。默认路径在用户目录，构造时不创建文件；UTF-8 追加；坏行不覆盖原文件。

- [ ] **Step 1: 写失败测试。** `tests/conftest.py` 以 autouse fixture 为每个测试设置临时 `EXAM_TUTOR_LEARNING_PATH`；显式路径仍可覆盖。断言测试中解析出的路径不是用户真实档案路径；若真实档案在测试前不存在，则测试后仍不得被创建，不读取已有的私人档案。断言 `tmp_path` 追加三种合法事件后新实例可读；两个 `LearningRecord` 对象指向同一路径时重复 `submission_id` / `draft_id` 不产生第二行；坏 JSON、无效 UTF-8、缺字段、非布尔正误行被跳过且有警告；额外 `answer`/`api_key` 键拒写；不同路径隔离；用 mock 写入/读取失败测试权限错误，不依赖 Windows 的 `chmod` 语义；环境变量与显式路径优先级均可测。

  ```python
  assert LearningRecord(tmp_path / "events.jsonl").read()[0][0]["kind"] == "reading_attempt"
  assert warnings  # 截断行不能静默进入统计
  ```
- [ ] **Step 2: 运行单测确认因模块不存在而失败。** `python -m pytest -q tests/test_learning_record.py`
- [ ] **Step 3: 实现 `LearningRecord`。** 使用 `pathlib`、`json`、`datetime`、`uuid` 等标准库；账本负责生成 `event_id`/`ts`，并在提交原稿事件中复用 `event_id` 为 `draft_id`。逐行容错读取，`UnicodeDecodeError` 只影响坏行，不使整个账本失效；保留有效事件的文件追加顺序。
- [ ] **Step 4: 跑同一单测至通过。** 再确认目录中没有生成个人档案或 API Key；Git 可用时只提交本任务文件。

### Task 2: 阅读判分写入长期账本

**Files:** Modify `retrieval/service.py`; test `tests/test_practice.py`, `tests/test_scenario_eval.py`; modify `tools/scenario_eval.py` 的练习构造路径。

**Interfaces:** `Service(config, session_id=None, learning_path: Path | None = None)` 创建 `LearningRecord`。`submit_practice_answer(...)` 沿用现有 `grade_attempt()`，成功后追加含 `kind="reading_attempt"`、原 `stage`、`filters`、`attempt_answer`、`attempt_correct` 的行；返回原判分加 `saved: bool`、账本 `event_id`，现有 `trace_id` 仍供当前会话解析使用。`practice_progress()` 改从账本读取并沿用 `summarize_attempts(events)`，追加 `history_warnings: list[str]` 供 UI 展示，不另造正确率算法。`practice_feedback(trace_id)` 保留现有会话语义；刷新后历史阅读只展示判分与“重新练/复盘”入口，不承诺恢复此前未持久化的模型解析。

- [ ] **Step 1: 写失败测试。** 同一路径的新 `Service` 恢复两次作答；未命中 KEYS 和“我不会”不写账；写盘失败仍返回 KEYS 判分但 `saved=False`；`practice_question()` 与 `submit_practice_answer()` 都不改 `LocationTable`；原有诊断 `Episode`、聊天定位不变。现有测试及 `run_practice_case()` 显式注入 `tmp_path`/临时目录；全局测试 fixture 兜底，禁止污染真实用户目录。

  ```python
  assert Service(None, learning_path=path).practice_progress()["attempt_count"] == 2
  assert failed_save["correct"] is True and failed_save["saved"] is False
  ```
- [ ] **Step 2: 跑针对性测试确认新断言失败。** `python -m pytest -q tests/test_practice.py tests/test_scenario_eval.py -k 'persist or practice'`
- [ ] **Step 3: 最小改动 `Service` 和场景构造。** 只在成功判分后写账；保存失败和诊断轨迹失败不能反过来改 KEYS 判定；旧 `answer_agrees` 不参与统计。
- [ ] **Step 4: 跑两份测试至通过。** 核对既有 `repeated_misses` 返回形状不被意外改成卷级坐标；Git 可用时提交本任务文件。

### Task 3: 作文/翻译安全题目与原稿提交

**Files:** Create `retrieval/draft_practice.py`; modify `retrieval/service.py`; test `tests/test_draft_practice.py`.

**Interfaces:** `get_draft_task(paper: dict, section: str) -> dict | None` 返回不含范文的 `{section, task_text, review_scope}`，其中 scope 只能是 `full`/`language_only`。翻译仅当 `translation_needs_review is False` 且中文原文非空时可用。作文使用非空 `writing` 作安全题目核心；首版仅把已逐字核实的 `2020_7_1`、`2020_9_1` 方向列入白名单，方向需与原缓存内容精确一致才能进入 `task_text` 并允许 `full`，其他情况统一 `language_only`；日后人工核实新卷再扩表。现有 chart/graph 题虽有标记，但图表图像未成为可验证的练习材料，必须 `language_only`，不能由图表词反推完整材料。`Service.draft_question(year, month, exam_set, section) -> dict | None` 只读缓存。`Service.submit_draft(year, month, exam_set, section, text, revision_of=None, submission_id: str | None = None) -> dict` 返回 `status` 为 `saved`/`unavailable`/`invalid`/`save_error`，成功时另有 `draft_id`；UI 每次表单动作提供并在重试中复用 `submission_id`，新的修改版生成新值；无 UI 的调用方省略该参数时由服务生成新值，不保证重复调用去重。先校验题目、文本和上一稿同卷同板块，再追加含 `draft_text`、`task_text` 快照、`review_scope`、`revision_of`、`submission_id` 的 `draft_submitted`；同一 `submission_id` 重试返回原 `draft_id`，不再追加。

- [ ] **Step 1: 写失败测试。** 安全视图无 `translation_sample`/`writing_sample`/`answer`；待核翻译不可提交；普通作文可提交；缺失、损坏、混入无关内容的 directions 及现有三套缺图的 chart/graph 作文只可语言评阅；空白和 10,001 字符被拒；跨卷 `revision_of` 被拒；同一提交动作重复到达只保留一稿，真正修改版保留两份全文和版本关联。

  ```python
  assert get_draft_task(paper, "translation") == {"section": "translation", "task_text": paper["translation"], "review_scope": "full"}
  assert "translation_sample" not in get_draft_task(paper, "translation")
  assert cross_paper_revision["status"] == "invalid"
  ```
- [ ] **Step 2: 跑测试确认失败。** `python -m pytest -q tests/test_draft_practice.py`
- [ ] **Step 3: 实现纯函数和两个 `Service` 方法。** 只读 `load_set_cached_only()`；题目快照随原稿保存；任何提交/查询不改 `LocationTable`。只让显式核实的方向通过白名单，其余降级，不让模型补造图表或指定要求。服务依赖 Task 1 的账本层幂等性，不在各 `Service` 实例上另加一把无效的锁。
- [ ] **Step 4: 跑测试至通过。** Git 可用时提交本任务文件。

### Task 4: DeepSeek 参考评语与失败重试

**Files:** Extend `retrieval/draft_practice.py`; modify `retrieval/service.py`; test `tests/test_draft_practice.py`.

**Interfaces:** `DraftReviewer(config).generate(section: str, task_text: str, draft_text: str, review_scope: str) -> dict` 单次模型调用并解析结构化反馈。`validate_feedback(raw: dict, section: str, draft_text: str, task_text: str) -> dict | None` 返回 `{overall, strengths, issues, priority}`；每个局部 issue 至少含 `category`、`quote`、`origin`、`suggestion`、`reason`，无效引文仅剔除该项；学生原稿引文须满足有意义的最小长度/完整词组规则，不能让单字符 `a`/`I` 凭偶然匹配过关；漏译 `origin="source"` 引文必须属于中文题目。`Service.review_draft(draft_id: str) -> dict` 只读已保存原稿，已有有效反馈直接复用，成功才追加一条 `feedback_ready`；状态只为 `ready`/`pending`/`feedback_not_saved`/`not_found`，同稿重试不追加原稿。`pending` 不追加“失败”事件；有 `draft_submitted` 但无有效 `feedback_ready` 即可在刷新后推导待评阅状态。

- [ ] **Step 1: 写失败测试。** 假模型返回语法/时态/用词/连贯性意见；无问题的有效反馈可过；失实及仅单字符偶然匹配的引文被剔除并有不完整提示；漏译来源引文验证；提示注入文本不能产生有效越权字段；模型异常/空结果时原稿仍可读取，刷新后仍显示待评阅并可重试；第二次点击不重复记反馈。

  ```python
  assert validated["issues"] == []  # 假模型只给不存在的英文引文
  assert retried["status"] == "ready" and saved_draft_count == 1
  assert "score" not in validated  # 假模型擅自输出的官方分数被丢弃
  ```
- [ ] **Step 2: 跑测试确认失败。** `python -m pytest -q tests/test_draft_practice.py -k feedback`
- [ ] **Step 3: 实现评阅。** 模型仅接收当前题目快照和当前稿，不接收账本/历史/密钥；明确禁止官方分数和整篇替写，翻译不同于参考译文不算错误。成功评语放入 `feedback_ready.feedback`；保存反馈失败时返回本次评语并标记 `feedback_not_saved`。
- [ ] **Step 4: 跑测试至通过。** 不用真实 DeepSeek 作为单测前提；Git 可用时提交本任务文件。

### Task 5: 三类进度和一个下一步

**Files:** Modify `retrieval/practice.py`, `retrieval/service.py`; test `tests/test_learning_progress.py`.

**Interfaces:** `summarize_learning(events: Sequence[Mapping[str, object]], preferred_section: str | None = None) -> dict` 在 `reading` 键下放现有 `summarize_attempts()` 结果，另返回 `repetition_groups: list[dict]`（每项 `{year, month, exam_set, question_number, wrong_count, latest_correct}`）、`writing_count`、`translation_count`、`writing_revisions`、`translation_revisions`、`latest_feedback_status`、`next_action: str`。`repetition_groups` 按完整卷级坐标聚合，`wrong_count` 是历史错次，`latest_correct` 只取该坐标按追加顺序的最新作答；推荐复盘只从 `wrong_count >= 2 and latest_correct is False` 或最近一次未纠正错题中选择。`Service.learning_progress(preferred_section: str | None = None) -> dict` 只读本机账本，追加 `history_warnings: list[str]`；不改 `reading.repeated_misses: list[int]` 兼容字段。页面进度只调用 `learning_progress()` 一次，不再并行调用 `practice_progress()` 重复读盘。

- [ ] **Step 1: 写失败测试。** 阅读正误与主观题次数互不混算；0–2、3–7、8+ 阅读阶段不变；最新已评阅稿推荐修订、最新待评稿（即有原稿无有效反馈）推荐重试、最新阅读错题推荐完整卷级复盘；同题最新一次答对后不再推荐；不同卷相同题号分成两个 `repetition_groups`；相同时间戳时仍按追加顺序判最新；用户指定板块优先；坏行警告可见；无记录只建议一项已收录练习。

  ```python
  assert summary["reading"]["attempt_count"] == 1 and summary["writing_count"] == 1
  assert "2024年12月第1套第36题" in summary["next_action"]
  ```
- [ ] **Step 2: 跑测试确认失败。** `python -m pytest -q tests/test_learning_progress.py`
- [ ] **Step 3: 实现纯统计和服务入口。** 统计只吃事件序列，不读路径；模型问题类别只能以“AI 建议”展示，不换算客观错误率。
- [ ] **Step 4: 跑测试至通过。** Git 可用时提交本任务文件。

### Task 6: Streamlit 三类练习与端到端回归

**Files:** Modify `streamlit_app.py`, `tests/test_streamlit_app.py`, `tools/scenario_eval.py`, `tests/test_scenario_eval.py`. 执行此任务前加载 `developing-with-streamlit` 并使用已安装 Streamlit 1.61.1 对应参考。

**Interfaces:** UI 默认保留阅读逐题练习；新增作文/翻译选择、卷级出题、`st.text_area` 原稿输入和显式表单提交。每次表单动作生成并在重跑/失败重试中复用 `submission_id`；提交返回 `draft_id` 后只调用一次 `review_draft()`；反馈失败展示“评阅未完成”和同稿重试；“修改后再交”传 `revision_of` 并生成新 `submission_id`。进度显示单次调用 `Service.learning_progress(preferred_section=用户明确选择的板块)`；会话状态只暂存当前展示稿，不充当历史档案。历史阅读展示正误和重练入口，不假装重开后仍有此前的 `practice_feedback(trace_id)` 模型解析。

- [ ] **Step 1: 写失败 AppTest/离线场景。** 阅读旧路径照常；作文/翻译提交前无范文；提交和修改显示两个版本；同一表单动作重跑不多计篇数；模型失败可重试且刷新后仍可找到待评稿；待核翻译和图表缺资料显示限制；界面标明本机保存位置、`EXAM_TUTOR_LEARNING_PATH` 可写路径配置、手动清理方式和 DeepSeek 传输，将旧“刷新后进度清零”提示改成“刷新后本机进度仍在”。同步更新 `tests/test_streamlit_app.py` 第 182 行含“刷新+进度”的断言；保留第 151–152 行及 `streamlit_app.py` 第 37 行的聊天定位提示，聊天短问法刷新后仍需完整定位。场景评测全部使用临时账本。

  ```python
  assert "参考译文" not in before_submission
  assert fake_service.draft_submit_count == 1 and fake_service.review_count == 1
  assert "刷新或重新打开页面后不会恢复" not in rendered_page
  ```
- [ ] **Step 2: 跑 UI 与场景测试确认失败。** `python -m pytest -q tests/test_streamlit_app.py tests/test_scenario_eval.py`
- [ ] **Step 3: 用原生 Streamlit 控件实现页面。** 保持旧阅读控件标签和聊天帮助的现有契约；只替换 `streamlit_app.py` 第 68 行的练习进度过期提示，不删第 37 行的聊天定位说明；首页文案区分“作文输入评阅已开放”和“作文范文聊天检索尚未上线”；不要把模型调用放在无条件重跑路径，也不要通过隐藏控件来保护答案。
- [ ] **Step 4: 跑新旧测试和离线场景。** `python -m pytest -q tests`，再运行 `python tools/scenario_eval.py --practice`；有 API Key 时可选择一次真实模型冒烟，但绝不把用户稿或密钥写进测试输出。报告通过数、跳过项和环境限制；Git 可用时提交本任务文件。

## Execution handoff

计划经用户审核后再实施。建议 Native 执行：六个任务共享同一个 `Service` 与账本接口，逐项本地红绿测试、最后独立复核。当前父级虚拟环境启动失败，但 Git 仓库存在且 `HEAD` 未出生；实施前先确认可工作的 Python 环境，不修改用户已有环境来掩盖问题。开头的 superpowers 执行技能在当前 Codex 环境中可用；若把计划交给缺少该技能的其他环境，应以其本地工作流执行测试步骤，不把技能名当产品依赖。
