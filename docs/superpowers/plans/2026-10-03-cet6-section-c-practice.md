# 六级仔细阅读（46–55 题）逐题练习施工计划

> **实施要求：** 审核本计划后，按任务逐项实施；每项先写失败测试、再写最小实现。不改动现有缓存和普通聊天讲题路径。

**目标：** 在现有 Streamlit「逐题练习」中加入仔细阅读：显示所属文章、题干及 A–D 选项；一次提交一个答案；提交后按缓存 KEYS 判分，并给出非官方的中文参考解析与下一步建议。

**架构：** 复用 `get_practice_item`、`grade_attempt`、`Service` 的作答事件和页面会话状态。新增的仅是 Section C 安全视图、A–D 判分分支、题型统计及专用反馈；不另建 Agent、存储层或解析管线。

**技术栈：** 现有 Python、pytest、Streamlit AppTest 和已安装的模型调用链；不增加依赖。

**设计依据：** 当前 `retrieval/structured.py` 的 `section_c.passages`、`get_section_c_question()`、`build_section_c_evidence()`，以及已上线的 26–45 题练习。以下将“阅读理解”解释为六级仔细阅读第 46–55 题；不包含听力或新的阅读题型。

## 已核对的现状与边界

- 初步盘点 38 套缓存，32 套的 Section C 各有两篇原文、10 道具备题干和答案选项的题；另 6 套不可据此开放。这个数字不是最终可练数量，运行时仍逐题校验原文、A–D 四项及 KEYS。
- 现有 `PRACTICE_PROMPT` 明确写的是「段落匹配」「正确段落」，不得直接套到仔细阅读；现有聊天用 `SECTION_C_PROMPT` 是八节讲解，也不等于逐题练习反馈。
- 出题接口绝不返回 `answer`、KEYS、正确选项标记或完整缓存对象。学生提交前只看到原文、题干、四个未标记选项。
- 判分只取缓存 KEYS；模型只能在判分后解释，不参与出题和改判。生成失败或内容与 KEYS 冲突时，仍显示代码判分，解析降级为明确标注的简短复盘提示。
- 一次作答只记录一条 attempt；「我不会」、无效选项及不可练题不记次。练习不改变聊天 `LocationTable`；会话进度仍只在当前浏览器会话有效。

## 文件分工

- `retrieval/practice.py`：新增 Section C 安全视图、A–D 判分，以及 `46-50` / `51-55` 统计分组。
- `retrieval/service.py`：沿用练习入口和轨迹；Section C 反馈从本题原文构建证据，固定判分与模型解析分离。
- `retrieval/answer_prompt.py`、`retrieval/generation.py`：增加简短的仔细阅读练习反馈模板和一次普通生成调用；现有段落匹配及八节聊天模板不变。
- `streamlit_app.py`：同一折叠区扩展题号至 55；根据安全视图显示文章/题干/A–D 选项。
- `tools/scenario_eval.py`：增加真实缓存的离线 Section C 练习场景。
- `tests/test_practice.py`、`tests/test_streamlit_app.py`、`tests/test_scenario_eval.py`：覆盖新分支和旧路径回归。

## 重点复核

1. 缺原文、题干、某个选项或 KEYS 不在 A–D：拒绝出题与判分，不记录 attempt。
2. 两篇文章并存：第 46–50 题只显示第一篇，第 51–55 题只显示第二篇；若同题重复出现在两篇，拒绝而不猜。
3. 学生出题后改了定位控件却没重新点「出题」：提交仍以屏幕上当前题的 `practice_target` 为准。
4. 学生选小写、空白、E 或空值：只接受规范化后的 A–D 单字母；无效输入不计次。
5. 模型失败、返回空白或声称另一答案：正误与标准答案不变，解析降级且不冒充官方解析。

---

### 任务 1：安全出题与确定性判分

**文件：** 修改 `retrieval/practice.py`；测试 `tests/test_practice.py`。

**接口：** 扩展现有 `get_practice_item(paper, question_number) -> dict | None`、`grade_attempt(paper, question_number, submitted_answer) -> dict | None`；Section C 安全视图固定为 `{question_number, passage_text, stem, options}`，其中 `options` 仅含 A–D 文本。判分仍返回 `{submitted, answer, correct}`。

- [ ] 先加测试：第一篇/第二篇正确选取；安全视图不含答案且修改返回对象不改变缓存；缺字段、重复题号、错误 KEYS 均拒绝；正确/错误/无效字母分支。
- [ ] 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_practice.py --basetemp=tmp\pytest-section-c-practice`，确认新断言先失败。
- [ ] 在 `get_practice_item` 增加 46–55 分支，逐题核验文章、题干、全部四项和 KEYS；只复制允许显示的字段。`grade_attempt` 只接受 A–D，调用 `get_section_c_question()` 读取答案。
- [ ] 重跑同一测试，确认新旧 26–45 路径全部通过。

### 任务 2：会话统计与判分后参考解析

**文件：** 修改 `retrieval/practice.py`、`retrieval/service.py`、`retrieval/answer_prompt.py`、`retrieval/generation.py`；测试 `tests/test_practice.py`。

**接口：** `summarize_attempts(events)` 新增 `by_range["46-50"]` 和 `by_range["51-55"]`；`Service.practice_feedback(trace_id)` 对 Section C 先重新核对已记录的作答/KEYS，再给中文参考解析和一条下一步建议。

- [ ] 先加测试：混合三种阅读题型的分组互不串账，2/3/7/8 次档位不变；反馈只引用当前题所属原文；模型不参与判分，失败/空白/冲突输出均降级；反馈调用不增加 attempt、不改 `LocationTable`。
- [ ] 运行任务 1 的 pytest 命令，确认新断言先失败。
- [ ] 复用 `build_section_c_evidence()` 供判分后解析；新增 Section C 练习专用提示词与一次生成方法，要求只比较本题四选项、标注「参考解析，非官方」、给一条可执行建议。代码先生成正误及标准答案，模型文本只作附加说明；加最小答案一致性检查，不通过即返回固定降级文案。Section B 的反馈路径保持原样。
- [ ] 重跑测试，确认通过。

### 任务 3：Streamlit 逐题交互与离线验收

**文件：** 修改 `streamlit_app.py`、`tools/scenario_eval.py`；测试 `tests/test_streamlit_app.py`、`tests/test_scenario_eval.py`。

**接口：** 现有练习题号选择扩展为 26–55；Section C 展示文章、题干、A–D 选项及「选择选项」控件，提交后显示 KEYS 正误与参考解析。保留已有 `practice_target` 绑定和「我不会」按钮。

- [ ] 先加 AppTest：提交前看不到标准答案；「我不会」不计次；改定位控件不影响当前题提交；提交后才显示答案。加离线场景覆盖一套真实缓存的 46 题和 51 题、一次答错、一次答对、一次无效提交。
- [ ] 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_streamlit_app.py tests\test_scenario_eval.py --basetemp=tmp\pytest-section-c-ui`，确认新断言先失败。
- [ ] 按安全视图类型分支显示，不从 UI 读取完整缓存；无效或缺失题显示「该套仔细阅读暂不能练习」。复用现有提交、鼓励、进度展示。
- [ ] 重跑 UI/场景测试；再运行 `& '..\.venv\Scripts\python.exe' -m pytest -q --basetemp=tmp\pytest-section-c-full` 和 `& '..\.venv\Scripts\python.exe' tools\scenario_eval.py --practice`。报告实测可练题/套数、测试通过数与既有警告。

## 本版不做

不批量提交 10 题、不生成新题、不做跨会话学习档案、不重建缺失缓存、不用模型猜 KEYS、不改变普通聊天的八节讲解。若将来要做「错因标签」统计，须先有可验证的结构化标签；本版只统计客观正误。
