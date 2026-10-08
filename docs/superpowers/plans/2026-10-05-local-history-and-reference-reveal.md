# 本机历史会话与参考答案确认展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan chooses native execution; do not dispatch subagents unless the user explicitly asks.

**Goal:** 在 Streamlit 左侧统一访问可恢复/可分叉的聊天与既有作文、翻译原稿，并在二次确认后才显示已核实的参考内容；本次不制作作文缓存。

**Architecture:** 聊天独立存为本机逐会话 JSON，原稿继续从 `LearningRecord` 的 JSONL 读取；侧栏只组合索引，不迁移原稿。参考内容由只读 `Service.reference_material` 按原题和审核标记取回，界面仅在第二次确认时调用。现有判分、评阅和聊天问答不改判。

**Tech Stack:** Python 标准库、现有 Streamlit 1.61.1、pytest 与 `streamlit.testing.v1.AppTest`。

**Spec:** `docs/superpowers/specs/2026-10-05-local-history-and-reference-reveal-design.md`；作文内容标准见 `docs/superpowers/specs/2026-10-03-cet6-writing-cache-design.md`。

## Global Constraints

- 本机单用户；不引入账号、云同步、数据库或新依赖。
- 聊天目录为现有 `LearningRecord.path.parent / "chats"`，所以 `EXAM_TUTOR_LEARNING_PATH` 仍控制本机位置。
- 不修改、迁移或删除 `learning_events.jsonl` 中的原稿、评语和阅读作答；旧聊天未存完整回复，不能伪造恢复。
- 分叉复制已完成的轮次，不撤销学习事件；恢复定位只用会话保存且通过字段校验的快照。
- 系统范文/译文及解析默认隐藏；练习/历史视图在第二次确认前不得调用参考接口，不要求先交稿；刷新或切换目标后重新隐藏。
- 仅明确审核通过且参考字段存在的缓存可以显示；作文/翻译练习及旧稿视图还须题目匹配。所有展示均标注“练习参考，非官方答案”；不得调用模型临时补答案。
- 底部聊天只有收到明确索取时才走现有答案路径；用户可在问句中写全卷坐标，也可在已恢复且无歧义的定位上短追问。打开历史会话不主动展示参考正文。本次二次确认仅覆盖作文/翻译练习与历史视图。
- 所有新测试必须写入临时本机目录；在 Task 1 的任何测试前，先升级 `tests/conftest.py`：测试前后用 SHA-256 对照真实学习档案及 `~/.exam-tutor/chats/` 下全部文件的存在性与内容，避免真实档案已存在时漏检。
- 本次不修改 `parsed_papers/`。未来作文内容任务修改题库之前，先对完整目录做可恢复备份；当前父仓库无 `HEAD`，题库未被跟踪。
- 父 Git 仓库无 `HEAD` 且 `.git` 不在可写根内；本计划不创建根提交。每任务用测试与文件清单作为检查点。

## Review Focus

1. 会话 JSON 损坏、ID 中带路径分隔符或内容超长时，跳过/拒绝并提示，不读取别的路径（Task 1 测）。
2. 两个标签页同时向同一会话提交，后提交者得到冲突提示而不覆盖先提交者（Task 1、3 测）。
3. 两篇同卷独立初稿分别列出；丢失父稿或跨卷 `revision_of` 独立成组、每篇恰好出现一次（Task 2 测）。
4. 切换练习、旧稿或会话及刷新后，确认状态失效且 `session_state` 不保留参考正文（Task 4 测）。
5. 缺字段、待核、题目不匹配或缓存缺失时不展示范文/解析，同时说明缘由；只允许空白归一化消除题目排版差异（Task 2、4 测）。

---

### Task 0: 真实本机档案的测试护栏

**Files:** Modify `tests/conftest.py`; create `tests/test_archive_guard.py`。

**Interfaces:** 在 `tests/conftest.py` 增加 `_snapshot_private_path(path: Path) -> tuple[bool, tuple[tuple[str, str], ...]]`：第一项为路径是否存在，第二项为按相对文件名排序的 SHA-256 摘要；文件自身用相对名 `"."`。现有 autouse fixture 保留 `EXAM_TUTOR_LEARNING_PATH=tmp_path/learning_events.jsonl`，并用该函数比较真实 `Path.home()/".exam-tutor"/"learning_events.jsonl"` 与同级 `chats/` 测试前后的快照，不把私人正文打印进测试输出。

- [ ] 先在 `tests/test_archive_guard.py` 使用隔离临时目录写快照测试：同样大小且被改动的内容仍产生不同摘要，目录中文件新增/删除也产生差异；绝不拿真实档案做破坏性试验。
- [ ] 运行 `python -m pytest -q tests/test_archive_guard.py`，确认快照函数尚不存在而失败。
- [ ] 升级 fixture；若真实目录测试前不存在，测试后也必须不存在；若存在则内容摘要必须相同。重跑快照测试与 `python -m pytest -q tests/test_learning_record.py`。

### Task 1: 本机聊天档案

**Files:** Create `memory/chat_archive.py`; create `tests/test_chat_archive.py`。

**Interfaces:** `ChatArchive(root: Path)`; `create() -> dict`; `list_threads() -> tuple[list[dict], list[str]]`; `load(thread_id: str) -> dict | None`; `append_turn(thread_id: str, user: str, assistant: str, location: dict, expected_revision: int) -> dict`（冲突抛专用异常）；`fork(thread_id: str, through_turn: int) -> dict`。文件只存应用生成的 32 位十六进制 ID、标题、UTC 时间、`revision`、可选 `parent_id`/`fork_turn`、`turns`。新会话标题为“新对话”，首轮完成时取用户原话去首尾空白后的前 30 字；本版不重命名。一轮含完整用户/助手文本与完成后的 `LocationTable` 快照；最大文本长度沿用输入 500 字，助手回复设 50_000 字上限。`append_turn`/`fork` 必须原子写入，按 revision 防覆盖；坏文件只报 warning，不删除。`list_threads()` 本版从逐会话 JSON 提取元数据，不增加第二份可失同步的索引；历史很大时列表可能变慢，记作 v1 已知限制。

- [ ] 先写测试：创建/首轮标题/追加/重新实例化恢复；任意轮分叉不改变父文件；两实例旧 revision 冲突；坏 JSON、非法 ID、错误定位类型和超长文本被拒绝或跳过。
- [ ] 运行 `python -m pytest -q tests/test_chat_archive.py`，确认因模块/行为缺失而失败。
- [ ] 用标准库 `json`、`pathlib`、`tempfile`/`os.replace` 实现上述接口；同进程用锁保护 compare-and-swap。只接受 `memory.session.FIELDS` 中的非空字段和正确类型。
- [ ] 重跑该文件确认通过，并记录改动和测试结果。

### Task 2: 旧原稿分组与只读参考接口

**Files:** Create `memory/draft_groups.py`; modify `retrieval/service.py`, `retrieval/draft_practice.py`; create `tests/test_draft_groups.py`, `tests/test_reference_material.py`。

**Interfaces:** `group_drafts(drafts: list[dict]) -> list[dict]` 返回按最近活动排序的根稿组，每组含 `root_id`、`section`、`filters`、`drafts`、`updated_at`；只有同板块/同卷且父稿存在的 `revision_of` 才连接，失联/跨卷父稿的子稿独立为根，每条输入恰好出现一次。`Service.reference_material(year: int, month: int, exam_set: int, section: str, expected_task_text: str) -> dict` 返回 `status`（`ready`、`missing`、`pending_review`、`task_mismatch`）、且仅 `ready` 包含 `sample`、`analysis`。比较 `get_draft_task(...)["task_text"]` 与 `expected_task_text` 前，仅用 `" ".join(text.split())` 折叠空白；语义不一致仍返回 `task_mismatch`。审核标记须明确为 `False`，两项参考字段须非空。翻译的审核标记和样文存在性规则要与 `_translation_answer` 一致，但旧稿特有的题目匹配不阻断聊天直接查询；非官方标注在两个入口都有。

- [ ] 先写测试：同卷独立初稿/真实修改链/失联或跨卷父稿/循环修改链，断言输入稿件 ID 与分组输出 ID 完全相等且无重复；参考接口对翻译已核缓存、待核、缺失、仅空白差异、实质题目不匹配和作文已核样例的返回；同卷待核在聊天与参考接口都不可展示。
- [ ] 运行两个目标测试文件，确认预期失败。
- [ ] 实现纯分组函数和只读服务方法；复用或抽取翻译的审核标记及样文存在性检查，但保留聊天在缺解析时仍可展示已核译文的现有行为。不触碰 `LocationTable`、学习事件、`DraftReviewer` 或模型调用。
- [ ] 重跑目标测试；确认原有 `tests/test_draft_practice.py` 与 `tests/test_translation.py` 仍通过。

### Task 3: 聊天/原稿统一侧栏与恢复、分叉

**Files:** Modify `streamlit_app.py`, `tests/test_streamlit_app.py`；复用 Task 1、2 接口。

**Interfaces:** 新增 `st.session_state.chat_archive`、`active_chat_id`、`history_view`、`chat_revision`；`messages` 继续为现有 `{"role", "content"}` 列表。侧栏把对话和原稿组按最近活动排序。新建、打开、分叉时重建 `messages` 与 `service.table`，旧稿条目显示现有 `draft_history()` 的题目、原稿和评语；“基于这版修改”复用现有 `draft_revision_of` 提交流程，并重置原稿输入控件的 key/内容，避免把上一份稿件带入新题。

- [ ] 先写 AppTest：新聊天提交后刷新自动恢复最近会话及完整问答；打开指定旧会话恢复定位、无定位时保持空表；从第一轮分叉保留父会话字节；恢复/分叉后的 `table.to_dict()` 恰好等于保存的合法非空快照（键是 `FIELDS` 的子集）；旧稿分组导航显示各版与评语；选择某版修改时输入框载入正确原稿、不串稿；冲突/存档失败有可见警告；原长历史展开区消失。测试用的 `FakeService` 要有真实 `LocationTable`，聊天档案注入临时目录。
- [ ] 运行相应 AppTest，确认 UI 行为缺失导致失败。
- [ ] 加 `st.sidebar` 的新建/历史列表及主区视图；首次页面加载自动打开最近更新的会话（无会话则空白）。每次 `service.process` 成功结束后再持久化一轮，失败则保留本轮屏显并提示未存档。对话恢复/分叉先验证快照只含 `memory.session.FIELDS` 的合法类型，再 `table.clear()` 与 `table.update(snapshot)`；不重放模型。
- [ ] 重跑 AppTest；更新旧测试中“刷新必失定位”的过时断言为“已存档会话可恢复”，保留无历史定位时的提示。

### Task 4: 两步确认与参考展示回归

**Files:** Modify `streamlit_app.py`, `tests/test_streamlit_app.py`; create `tests/test_writing_reference_cache.py`。不修改 `parsed_papers/*.json`。

**Interfaces:** UI 目标键 `(section, year, month, exam_set, task_text, optional_draft_id)`；状态仅 `hidden` / `confirming` / `revealed`，不把正文存到 session state。`hidden` 点“查看参考答案与解析”仅进入确认态；点“取消”恢复隐藏；点“确认查看”首次调用 Task 2 接口，之后只在同一目标保持 `revealed` 时按需重读。切换目标、聊天、刷新均隐藏。`writing_needs_review` 缺失或不为 `False` 的卷都视为待核；本版 38 套作文均无已核范文，不向题库补写字段或样文。

- [ ] 先写 AppTest：未确认、首次点击、取消都未调用参考接口；第二次确认才调用且显示非官方标签；确认后的普通重跑仍可见、切换/刷新后隐藏；待核/缺内容显示明确降级。
- [ ] 写只读缓存覆盖测试：当前 38 套作文缺审核标记均 fail-closed；对构造的 `False` 样例，只有样文、中文解析非空且题目匹配才返回 `ready`；`True` 或缺失均不得公开。
- [ ] 跑新增 UI 测试确认预期失败；只读缓存测试若现有 fail-closed 规则已满足，可直接作为回归检查，不为追求红灯篡改题库。
- [ ] 实现 UI 门槛；作文缺失时明确提示“暂无已核实参考范文”，不在本任务撰写范文或修改题库。
- [ ] 跑 `python -m pytest -q tests/test_learning_record.py tests/test_chat_archive.py tests/test_draft_groups.py tests/test_reference_material.py tests/test_writing_reference_cache.py tests/test_streamlit_app.py`，再跑全量 `python -m pytest -q`；记录通过、失败和 38 套作文仍待内容任务的事实，并核查真实学习档案与聊天目录哈希未变。

## Execution Handoff

计划完成后，先由用户核对本计划及执行方式，再用 `superpowers:executing-plans` 逐任务实施。Task 0 的测试护栏必须早于 Task 1 的任何新测试。作文范文和中文解析另按作文缓存设计做独立内容任务，动题库前先备份。由于任务间接口连续依赖，建议由我在当前会话原生执行，不用子代理；父仓库无首个提交时不强行提交。
