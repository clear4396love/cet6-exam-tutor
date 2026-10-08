# Progress Log

## Session: 2026-09-29 Phase 10 智谱 OCR 对比预检

### Current Status
- **Phase:** 10 - 三套卷子智谱 OCR 与 Paddle 对比（Complete）

### Actions Taken
- 复核 Phase 9 已完成，并在当前计划中追加 Phase 10。
- 核对目标 PDF、Paddle 缓存页数及目标 `_zhipu` 目录：三套 PDF 均存在、Paddle 缓存均完整、三个 `_zhipu` 目录均不存在。
- 核对环境时确认 `.env` 中令牌可用（未打印令牌）；项目 `.venv` 缺少 `zai` 模块。用户授权后安装 `zai-sdk==0.2.3` 到项目 `.venv`，未改 `requirements.txt`。
- 智谱客户端及 `layout_parsing.create` 导入/接口检查通过。
- 智谱 OCR 已为三套目标卷完成并落入各自新的 `_zhipu` 目录：2022_12_3 8 页、2023_3_1 10 页、2025_12_2 8 页；每卷 meta 页数与 doc 数一致。
- 2022_12_3 与 2023_3_1 的 A/B/C 同解析器对比完成，三节答案串均与 Paddle 及正式题库一致。首轮处理 2025_12_2 时内联路径有一字写错，Paddle 缓存保护后在上传前报 `FileNotFoundError`；修正后仅需重跑该卷。
- 三套全部解析比较完成：三方 A/B/C 答案串全一致；A 词库和答案词全一致，B 题干/答案全一致，C 结构与答案完整，只有少数标点/单词 OCR 差异（2025_12_2 第 54 题 `given`/`giver`）。本轮已达到结构与答案对比目标，差异尚未据原卷视觉确认。
- 对照 `parsed_papers/2025_12_2.json` 后确认第 54 题正式题干是 `advice giver`，智谱与正式缓存一致，Paddle 误识为 `advice given`。`parsed_papers` 最新 mtime 仍为 `2022_12_3.json 2026-09-24 14:19:59`；三份 Paddle 缓存仍完整，未调用 Paddle 上传。
- 全量测试 `python -m pytest -q --ignore=tmp --basetemp=tmp/pytest-phase10`：**68 passed, 1 warning in 6.01s**；警告为既有 `langchain-community` 弃用提示。清除了本轮创建的 `tmp/pytest-phase10`。
- `requirements.txt` 的修改时间仍为 2026-09-24 14:47:26（本轮未改）；SDK 只在 `.venv` 安装。正式题库 JSON 共 38 个，最新仍为 `2022_12_3.json`（2026-09-24 14:19:59）。

### Errors
| Error | Resolution |
|-------|------------|
| 智谱代码导入依赖 `zai`，当前 `.venv` 未安装该模块 | 用户授权后仅在项目 `.venv` 安装官方 SDK；未改依赖清单 |
| 首轮对比脚本中的 2025_12_2 文件名误用繁体“題” | Paddle `pages()` 缺文件检查报错、没有上传；修正路径后只重跑该卷 |
| 首次组装 Section C 差异摘要脚本时出现缩进语法错误 | 未执行解析；简化脚本后重跑并得到逐题差异 |
| 2025_12_2 首次对比脚本对 PDF 名称写错一个汉字 | Paddle 本地缓存函数因路径不存在而在打开文件时报错，未发 OCR；改用 ASCII glob 精确匹配后正常读取两侧缓存 |

## Session: 2026-09-24

### Current Status
- **Phase:** Complete
- **Started:** 2026-09-24

### Actions Taken
- 完成 2020_7_1 首轮 OCR 试验并输出 eval/ocr_spike/2020_7_1_section_b.json。
- 新增 Section B OCR 格式测试，修改段标和答案区间解析。
- 开始筛选另外 3 套验证卷。
- 检查 2021_6_3、2023_6_3、2022_9_1 的 OCR 缓存和答案页。
- 2021_6_3 与 2022_9_1 标记 skipped_no_answers；2023_6_3 进入 HTML KEYS 解析修复。
- 新增 HTML KEYS 回归测试并复用 Paddle 表格提取逻辑；2023_6_3 验证通过。
- 完成 2024_12_2 云端 OCR 和结构验收，作为第 2 个扩展成功样本。
- 完成 2024_12_1 云端 OCR 和结构验收，作为第 3 个扩展成功样本。
- 已生成 2023_6_3、2024_12_2、2024_12_1 三份独立试验 JSON。
- 已对照原 PDF 抽查三套 Section B 页面与答案页，三组答案均与试验 JSON 一致。
- 自动检查三套均为 10 题，所有答案段落都存在。
- 全量 pytest 通过；临时 PDF 渲染图已删除，OCR 缓存和试验 JSON 保留。

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| 全量 pytest | 无回归 | 52 passed, 1 warning | passed |

### Errors
| Error | Resolution |
|-------|------------|
| Paddle token 最初未在项目根目录 | 本轮从父级 .env 显式加载；未修改产品代码 |
| 三套真实缓存复跑命令出现 Python 引号语法错误 | 改成先计算 answer_text 再输出；未执行解析和写盘 |
| 计划状态补丁引用错文件位置 | 补丁整体被拒绝，重新读取后按正确文件更新 |
| PDF 渲染出现 Symbol 字体警告 | 抽查图仍清晰可读，不影响英文题目与答案核对 |

## Session: 2026-09-24 定点复核

### Current Status
- **Phase:** Complete

### Actions Taken
- 按用户指定固定选择 2020_12_2 和 2021_6_3，不再随机抽卷。
- 确认两套均已有 PaddleOCR 缓存；2020_12_2 有答案表，2021_6_3 没有答案页。
- 复用真实解析器验收：2020_12_2 为 11 段/10 题/答案 EICKDGAFIB，所有答案段存在；2021_6_3 为 12 段/10 题/0 个答案，按规则跳过。
- 已对照原 PDF：2020_12_2 答案页与解析结果一致；2021_6_3 末页直接结束于翻译，确认没有答案页。
- 已生成 `eval/ocr_spike/2020_12_2_section_b.json`；未生成 2021_6_3 半成品。
- 全量测试 52 passed, 1 warning；临时 PDF 渲染目录已删除。

### Errors
| Error | Resolution |
|-------|------------|
| 当前目录的 `.git` 不是有效仓库，git diff --stat 无法执行 | 不改 Git 配置，继续用文件检查和测试验证 |

## Session: 2026-09-24 Section A 随机验证

### Current Status
- **Phase:** 7 - 随机验证 3 套 Section A —— Complete
- **完成日期:** 2026-09-27

### Actions Taken
- 确定采用固定随机种子，排除 5 套重复卷；无答案页继续跳过，直到取得 3 套完整样本。
- 记录固定随机种子 `20260924-section-a` 和候选顺序；首个候选为已知无答案的 2022_9_1。
- 检查现有 Section A 解析器，决定不调用会写正式题库的 `save()`。
- 用 5 套真实缓存稳定复现 `parsed=False`，并把故障定位到空位格式、HTML 词库和 26-35 HTML 答案范围三处契约差异。
- 新增 3 条 Section A OCR 契约测试并确认 RED（3 failed）；最小修改后与 Section B OCR 测试合计 7 passed。
- 重新运行真实缓存：2020_7_1、2021_12_1 成为前两套完整样本；2022_9_1、2020_9_2 因无答案跳过。
- 确认 2025_12_2 有答案页；授权后完成 8 页 PaddleOCR 缓存。
- 2025_12_2 结构验收通过，成为第 3 套完整样本；已输出三份 `*_section_a.json` 到 `eval/ocr_spike`。
- 重新读取三份 JSON，15 词/10 题/答案串/答案词映射全部通过。
- 收尾复核发现 `2020_7_1` 的卷面答案与正文语义冲突 → 记为 `answer_conflict`，保留证据 JSON，不改正式题库，不计入成功样本。
- 收尾复核发现 `section_a.text` 尾部混入词库 HTML → 先加断言确认 RED（`1 failed, 6 passed`），再用 `chunk.rfind("<table", 0, stop)` 最小修改转 GREEN（定向 `7 passed, 1 warning in 0.29s`）。
- 用 `2022_6_1` 补位：只用本地 paddle md 缓存重新解析（命令输出 `[paddle] 复用缓存 …`，未上传任何 PDF），生成 `eval/ocr_spike/2022_6_1_section_a.json`，并顺带刷新 2021_12_1、2025_12_2 两份 spike JSON。
- 三份刷新结果与来源 md 直接对账（词库逐词、KEYS 行逐字母），四份 JSON 六项结构检查全部通过且 `text` 均不含 `<table`。
- 核对 `parsed_papers` 未被改动（最新 mtime 仍为 `2026/9/24 14:19:59`）；`tmp/pdfs/` 本轮为空，无本轮生成的子目录。

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `pytest tests/test_section_a_ocr.py tests/test_section_b_ocr.py -q` | 7 passed | 7 passed, 1 warning in 0.29s | passed |
| `pytest -q`（原样） | 约 55 passed | 51 passed, 4 errors（全为 `tmp_path` fixture 的环境权限错误） | 环境问题 |
| `pytest -q --basetemp=tmp/pytest-tmp` | 约 55 passed | 55 passed, 1 warning in 1.96s | passed |

### Errors
| Error | Resolution |
|-------|------------|
| 父仓库对当前沙箱用户报 dubious ownership | 不修改用户的全局 Git 配置，改用文件和测试结果验收 |
| 缓存盘点命令把 `foreach` 直接接到管道，PowerShell 报空管道 | 改用 `$rows = foreach (...) {...}` 后再输出，不重复原命令 |
| Section A 批量检查的内联 f-string 转义失败 | 不执行解析；改成预先计算变量后用 `format()` 输出 |
| 检查 2025_12_2 时发现 `pdftotext` 不可用 | 保留 `pdfinfo` 的 8 页结果，改用已有 PyMuPDF + PDF 渲染 |
| 沙箱内 PaddleOCR 请求被 WinError 10013 拒绝 | 按权限规则升级后重跑成功，未改产品代码 |
| 临时脚本 `from sectionB_load import …` 报 `ModuleNotFoundError: No module named 'reading'` | 脚本里同时把项目根目录加入 `sys.path`，未改产品代码 |
| 2020_7_1 卷面答案与正文语义冲突 | 记为 `answer_conflict`：保留 OCR 证据、不改 parsed_papers、不推断答案、不计入成功样本 |
| `pytest -q` 四个 `test_paddle_ocr` 用例在 setup 报 `PermissionError [WinError 5] …Temp\pytest-of-86195` | 环境残留目录（2026-09-24 19:55 由另一安全上下文创建），连 `Get-Acl`/列举/删除都被拒；与本轮改动无关，加 `--basetemp` 重跑即 55 passed |
| 项目 `.venv\Scripts\python.exe` 启动报 `No Python at '…\uv\python\cpython-3.11.15…'` | 未手改 `pyvenv.cfg`；经用户授权改用同一解释器的 LocalCache 副本 + `.venv\Lib\site-packages` 的 `PYTHONPATH` 执行 |

## Session: 2026-09-27 Phase 8 失败卷重扫 + 新旧对照

### Current Status
- **Phase:** 8 - Section A 失败卷重扫 + 新旧对照（6 套）—— Complete
- **完成日期:** 2026-09-27

### Actions Taken
- 新增 `eval/batch_section_a.py`（本轮唯一新增文件）：OCR 直接走 `submit → wait → download`，原始 markdown 不经 `clean()` 落 `eval/ocr_spike/fresh_ocr/<卷>/doc_NNN.md` + `meta.json`；旧侧先验 `meta["pages"] == len(doc_*.md)` 才调 `pdf_load()`。
- 范围写死 6 卷（5 失败卷 + 对照卷 2022_6_1）；重复卷、无答案卷、2020_7_1、2020_9_2、2025_6_2 全程未发任何 OCR 请求。
- 先 `--limit 1` 冒烟跑通全链路，再跑满 6 卷；续跑按新目录 md 数 vs 新 `meta["pages"]`（不是 PDF 页数）判断。
- 七条门禁（词库 A–O ×15 / 题号 26–35 / 10 题答案齐 / 答案⊆词库 / answer_word 一致 / text 无 `<table` / 答案串与 OCR 答案页一致）全部独立实现：第 7 条按 `<tr>`/`<td>` 拆行去标签后配对，范围式答案单独解析。
- 逐卷四项对照（OCR 结果数 / 原始正文相似度 / 词库 / 答案串），差异写 `_report.json`。
- 根因定位：`define()` 的 `Reading Comprehension` 字面锚点在 2021_12_2 只于答案页出现、在 2021_6_1 整卷缺失；2022_12_3 / 2023_6_3 切块正确但 `split_passages()` 依赖的 Directions 原句整卷 0 命中；2020_12_2 两轮 OCR 逐字节相同、词库稳定把 `I.` 读成 `B.`。
- 核对旧缓存与正式题库未被写入：`parsed_papers/**` 最新 mtime 仍为 2026-09-24 14:19:59，`databases/**` 最新 mtime 仍为 2026-09-24 20:07:58（Phase 7 的 2025_12_2），本轮文件全在 `eval/ocr_spike/fresh_ocr/` 下。

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `./.venv/Scripts/python.exe -m pytest -q`（按计划先实测） | 可运行 | `No Python at '…uv\python\cpython-3.11.15-windows-x86_64-none\python.exe'` | 解释器不可用，如实记录 |
| 替代解释器 `-m pytest -q --ignore=tmp --basetemp=tmp/pytest-tmp` | 无回归 | **56 passed, 1 warning in 2.66s** | passed |
| OCR 耗时 | 6 卷 59 个版面结果 | 首轮 4 卷 18:10:18–18:12:11 落盘；2023_6_3 与 2022_6_1 于 18:25 重试成功（2022_6_1 上传 11 页 14.0s） | passed |

### Errors
| Error | Resolution |
|-------|------------|
| 2023_6_3 云端 `running 0/8` 卡 655.1s 后 `SSLEOFError`；2022_6_1 submit 阶段同报 `SSLEOFError` | 判为云端瞬断；不新增重试框架，原样重跑同一命令，第 3 次两卷均 `done` |
| 项目解释器按计划实测仍报 `No Python at …` | 如实记录，改用同一解释器的 LocalCache 副本 + `.venv\Lib\site-packages`，未手改 `pyvenv.cfg` |
| 5 套失败卷重扫后仍 parse_failed | 按计划只记录、不改 `reading/**`：4 套判为解析器规则限制，1 套判为稳定 OCR 字母误识 |

## Session: 2026-09-28 Phase 9 修两处单点依赖（3 套）

### Current Status
- **Phase:** 9 - 修 Section A 两处单点依赖（3 套）+ 2020_12_2 只留证据 —— Complete
- **完成日期:** 2026-09-28

### Actions Taken
- 先按计划改测试：`tests/test_section_a_ocr.py` 追加 5 条合成 fixture 测试（2021_12_2 / 2022_12_3 / 2023_6_3 / 2021_6_1 形状 + 2022_6_1 对照），每条断言到答案串级别。
- 首轮实测 `3 failed, 6 passed`（3 条 RED 均为 `extract()` 返回 None），与预期一致。
- 最小修改 `reading/sectionA_load.py`：加 `_blanks_ready()`、覆写 `define()`（父类结果凑齐 26–35 就直接返回；不完整且文档出现过 `Reading Comprehension` 字面时按空位结构兜底：26 前最近 `Section A` → 35 后最近 `Section B`/`Section C`/文末），`split_passages()` 在 `Directions` 0 命中时返回整块去标题。
- 定向 `13 passed`（Section A 9 + Section B 4，Section B 未被带坏）；全量 `61 passed, 1 warning`。
- `eval/batch_section_a.py` 整份未改动，原样重跑：6 卷全部 `[reuse] … 跳过 OCR`（新结果目录已完整，未发任何 OCR 请求），逐卷对照 Phase 8 的 `_report.json`。
- 另跑 26 卷旧缓存「原版解析 vs 修复后解析」逐字段（`q_from`/`q_to`/`text`/`words`/`questions`）对比：23 卷相同、3 卷变化。
- 核对 `parsed_papers/**`（38 个 json，最新 `2022_12_3.json` 2026-09-24 14:19:59）与 `databases/**`（343 个文件，最新 `doc_007.json` 2026-09-24 20:07:58）mtime 未变；本轮只写 `eval/ocr_spike/fresh_ocr/`。临时脚本与 `tmp/pytest-tmp` 用完已删。

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `pytest tests/test_section_a_ocr.py -q`（改代码前） | 3 RED / 2 GREEN | 3 failed, 6 passed, 1 warning in 0.59s | 符合预期 |
| `pytest tests/test_section_a_ocr.py tests/test_section_b_ocr.py -q`（改代码后） | 全绿 | 13 passed, 1 warning in 0.40s | passed |
| `./.venv/Scripts/python.exe -m pytest -q`（按计划先实测） | 可运行 | `No Python at '…uv\python\cpython-3.11.15-windows-x86_64-none\python.exe'` | 解释器不可用，如实记录 |
| 替代解释器 `-m pytest -q --ignore=tmp --basetemp=tmp/pytest-tmp` | 无回归 | **61 passed, 1 warning in 4.50s**（Phase 8 为 56 passed，+5 条新测试） | passed |
| `eval/batch_section_a.py` 重跑（6 卷真实缓存） | 恰好 3 套翻转 | success 3 套 `2021_12_2 / 2022_12_3 / 2022_6_1`；parse_failed 3 套 `2020_12_2 / 2021_6_1 / 2023_6_3` | 符合预期 |
| 26 卷「原版 vs 修复后」逐字段 | 只 3 卷变化 | identical 23 / changed 3（全部 `None->parsed`） | passed |

### Errors
| Error | Resolution |
|-------|------------|
| 项目解释器按计划实测仍报 `No Python at …` | 如实记录，改用同一解释器 LocalCache 副本 + `.venv\Lib\site-packages`，未手改 `pyvenv.cfg` |
| 替代解释器 stdout 为 gbk，解析器/`pytest` 打的中文在终端显示成乱码（如 `�ʿ�ȱ`） | 只影响显示层：判定一律读 `_report.json` 与 `parsed_papers/*.json` 的实际字段值，不改产品代码、不换编码 |
| 对照正式题库时先按 `CET6_*.json` 找文件，`FileNotFoundError` | `parsed_papers/` 下文件实际按 `2020_12_1.json` 命名；改用文件名 stem 当 key 重新对账 |
