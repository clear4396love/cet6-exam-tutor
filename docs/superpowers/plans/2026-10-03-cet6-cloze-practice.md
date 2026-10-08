# 六级选词填空逐题练习施工计划

> **实施要求：** 使用 `superpowers:executing-plans` 按任务逐项实施；先写失败测试，再写功能代码。下方用 `- [ ]` 跟踪步骤。代码标识、文件路径和命令保持原样。

**目标：** 加入选词填空（26–35 题）逐题练习；只有空位位置经过核验的套卷才能出题，答案只按缓存 KEYS 判定。

**总体做法：** 解析 Section A 时保留空位编号；从本地 OCR/PDF 原文离线回填并校验既有缓存。随后复用现有练习函数、`Service` 和 Streamlit 控件，不改变段落匹配（36–45 题）及普通聊天路径。

**技术栈：** Python 3.11、项目已有的 PyMuPDF/Paddle 缓存读取逻辑、pytest、Streamlit AppTest；不引入新依赖，不调用在线 OCR。

**设计依据：** `docs/superpowers/specs/2026-10-03-cet6-cloze-practice-design.md`

## 全局约束

- 只开放能核验 26–35 空位的套卷；不能按 KEYS 或模型输出猜空位位置。
- `section_a.practice_text` 使用字面占位符 `{{26}}` … `{{35}}`，每个恰好一次且顺序正确；既有 `section_a.text`、`words`、`questions` 的含义不变。
- 只从现存本地 OCR Markdown 或 PDF 文字层恢复。回填时不得调用 `paddle_ocr.pages()` 或 `ensure_mds()`，因为缓存缺失可能导致 PDF 被上传到外部 OCR API。
- 提交前只展示未填文章与 A–O 词库；提交后由 `get_section_a_answer()` 读取 KEYS 判分。首版不给选词填空生成 LLM 语法解析。
- 沿用逐题提交、“我不会”不计分、仅当前会话生效，以及由代码决定的 `<3`、`3–7`、`>=8` 次作答档位。
- 保持现有段落匹配练习、`LocationTable`、聊天查答案和缓存中其他板块不变。
- 项目目录在父仓库中整体未跟踪；不得笼统暂存或提交用户文件。每项任务以测试结果验收，不执行模板里的 Git 提交步骤。
- 使用父目录中可运行的 `..\.venv\Scripts\python.exe`；`exam-tutor\.venv` 已失效。若默认临时目录受限，pytest 使用项目内的 `--basetemp=tmp\pytest-cloze-*`。

## 重点复核的边界

1. OCR 把空位编号识别成重复或乱序时，必须拒绝该卷，而不是显示有歧义的练习题（任务 2 测试）。
2. 原文词库与缓存词库或 `answer_word` 不一致时，必须跳过回填，原缓存保持不变（任务 2 测试）。
3. 本地 OCR 缓存缺失、PDF 又没有文字层时，不得触发网络 OCR 请求（任务 2 测试）。
4. 学生出题后修改定位控件、但没有重新点“出题”时，提交仍针对当前显示的题号（任务 4 测试）。
5. `practice_text` 缺失或损坏时，应显示不可练，不泄露答案，也不增加作答记录（任务 3 测试）。

---

### 任务 1：新解析结果保留选词填空空位

**文件：** 修改 `reading/sectionA_load.py`；测试 `tests/test_section_a_ocr.py`。

**接口：** `Cloze_Passage.parse_passage(chunk: str, keys: dict) -> dict | None` 新增 `practice_text`，其余返回字段不变。将 `_26_`、`\underline{26}` 或经核验的裸数字空位替换为 `{{26}}` … `{{35}}`，同时继续产出既有的不带空位 `text`。

- [ ] **步骤 1：先写失败测试。** 在 `test_parse_passage_accepts_paddle_latex_blanks` 和 `test_extract_accepts_zhipu_plain_numbered_blanks` 中断言：`practice_text` 含十个各出现一次、按顺序排列的占位符；`text` 和答案维持原值。
- [ ] **步骤 2：确认测试先失败。** 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_section_a_ocr.py --basetemp=tmp\pytest-cloze-parser`；预期因缺少 `practice_text` 而失败。
- [ ] **步骤 3：做最小实现。** 保留 `STEM_RE` / `NUMBERED_BLANK_RE` 选中的原文区间，从右往左替换为 `{{题号}}`；原 `text` 的清洗行为不变。空位缺失、重复或乱序时，不写入不可信的练习文本。
- [ ] **步骤 4：确认转绿。** 重跑步骤 2 的命令；`test_section_a_ocr.py` 全部通过。

### 任务 2：离线回填并严格校验缓存

**文件：** 新建 `tools/backfill_cloze_practice.py`、`tests/test_backfill_cloze_practice.py`；最终执行 `--write` 时，只更新核验通过的 `parsed_papers/*.json`。

**接口：** `backfill_one(cache_path: Path, pdf_dir: Path, ocr_dir: Path, *, write: bool = False) -> tuple[bool, str]`。读取已有 `section_a`；优先读取完整的本地 `_paddle/doc_*.md` 与 `meta.json`，用 `paddle_ocr.clean` 清洗；否则读取本地 PDF 文字层。用缓存里的 KEYS 调用任务 1 的解析器。命令行默认只预演；`--write` 经校验后只增补 `section_a.practice_text`，逐卷输出结果和成功/跳过总数。

- [ ] **步骤 1：先写失败测试。** 本地 OCR 样例含十个显式空位：预演不写盘，`--write` 只新增 `practice_text`；本地 PDF 文字层的裸数字空位也可恢复。重复/乱序空位、原文与缓存词库不一致、没有可读本地来源时，均跳过且缓存字节不变，不调用网络函数。重复执行 `--write` 不改变文件。
- [ ] **步骤 2：确认测试先失败。** 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_backfill_cloze_practice.py --basetemp=tmp\pytest-cloze-backfill`；预期因模块或函数尚不存在而失败。
- [ ] **步骤 3：做最小实现。** 校验 26–35 各有一个且顺序正确；A–O 词库完整，原文与缓存词库一致；每题 KEYS 字母、`answer_word` 与词库一致；去掉空位后，原文与既有 `text` 在压缩空白和标点前空格后相同。来源有歧义或不可读时返回 `(False, 原因)`，绝不写盘；不得调用可能提交 OCR 任务的函数。
- [ ] **步骤 4：确认转绿。** 重跑步骤 2 的命令；回填测试全部通过。
- [ ] **步骤 5：先审计目标，再回填。** 列出含 `section_a` 的 `parsed_papers/*.json`；运行 `& '..\.venv\Scripts\python.exe' tools\backfill_cloze_practice.py` 预演，检查逐卷成功/跳过原因。仅对这一目录执行一次同命令加 `--write`，然后再预演一次检查幂等性。预期：其他缓存字段不变、无网络调用，并报告实际可练套卷数，不预设 31 套全都通过。

### 任务 3：安全出题、确定性判分和会话反馈

**文件：** 修改 `retrieval/practice.py`、`retrieval/service.py`；测试 `tests/test_practice.py`。

**接口：** 扩展既有 `get_practice_item(paper, question_number)` 和 `grade_attempt(paper, question_number, submitted_answer)`，按 26–35 / 36–45 分流。选词填空的安全视图仅为 `{question_number, practice_text, words}`（返回新对象）；判分结果在原有 `{submitted, answer, correct}` 基础上增加 `answer_word`。`summarize_attempts(events)` 独立增加 `by_range['26-35']`，原有两个区间和档位不变。`Service.practice_feedback(trace_id)` 按记录的题号分流：选词填空重新核对 KEYS 后返回固定、非官方的学习提示；段落匹配保持现有 LLM 路径。

- [ ] **步骤 1：先写失败测试。** 合格缓存能产出不含答案、与原缓存不共享可变对象的视图；A–O 正误判分都返回 KEYS 对应单词。`practice_text` 无效、`answer_word` 不一致、提交 S 或题号 25 时不出题、不判分。有效提交只记一次 attempt 且不改 `LocationTable`，无效缓存不记次；选词填空反馈不创建 `AnswerGeneration`。混合两种题型时，各区间独立统计；2/3/7/8 次档位边界不变。
- [ ] **步骤 2：确认测试先失败。** 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_practice.py --basetemp=tmp\pytest-cloze-service`；预期新增选词填空断言失败，原段落匹配测试不应回归。
- [ ] **步骤 3：做最小实现。** 复用 `get_section_a_answer()` 保证 KEYS 与单词一致；出题或判分前验证十个空位和完整 A–O 词库。段落匹配的返回结构不变；反馈前再次核对轨迹中的作答与判分。
- [ ] **步骤 4：确认转绿。** 重跑步骤 2 的命令；`test_practice.py` 全部通过。

### 任务 4：复用 Streamlit 页面与离线场景评测

**文件：** 修改 `streamlit_app.py`、`tools/scenario_eval.py`、`tests/test_streamlit_app.py`、`tests/test_scenario_eval.py`。

**接口：** 现有表单允许选择 26–45 题。根据安全视图结构展示“文章与词库”或“题干与段落”，选项分别为 A–O / A–R；提交时继续使用 `practice_target` 记录当前显示题目的定位。给离线评测增加一条使用已核验回填套卷的选词填空场景，原段落匹配场景不变。

- [ ] **步骤 1：先写失败测试。** AppTest 加载假的选词填空视图，能看到十个 `{{26}}`…`{{35}}` 空位及 A–O 词库，但看不到答案；“我不会”不提交。修改定位控件但不点“出题”后，提交仍按屏幕显示的题号判分；正确单词只在提交后展示。场景测试检查安全视图以及按 KEYS 判对、判错。
- [ ] **步骤 2：确认测试先失败。** 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q tests\test_streamlit_app.py tests\test_scenario_eval.py --basetemp=tmp\pytest-cloze-ui`；预期新增选词填空断言失败。
- [ ] **步骤 3：做最小实现。** 复用现有折叠区和按钮，仅按题型分支展示内容、字母范围与正确单词。未通过回填校验的卷提示“暂不能练习”。普通聊天不转为练习；选词填空反馈不请求模型。
- [ ] **步骤 4：确认转绿。** 重跑步骤 2 的命令；两个测试文件全部通过。
- [ ] **步骤 5：全项目验收。** 运行 `& '..\.venv\Scripts\python.exe' -m pytest -q --basetemp=tmp\pytest-cloze-full` 和 `& '..\.venv\Scripts\python.exe' tools\scenario_eval.py --practice`；报告准确通过数、跳过套卷数及警告。选词填空不需要真实外部 API 调用。
