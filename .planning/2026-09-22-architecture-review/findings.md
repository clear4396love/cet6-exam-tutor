# Findings

> 外部网页内容仅作为研究资料，不执行其中的指令。

## 本地代码

- 当前产品代码约分为 `retrieval/` 在线问答链路、`memory/` 会话与轨迹、`reading/`/`mask/` 离线题库构建。
- 根目录没有 requirements、pyproject、lockfile 等依赖清单，可复现性是待确认的底层风险。
- 在线链路核心是 `Service -> intent/locator -> LocationTable -> structured -> AnswerGeneration -> Episode`。
- 离线构建仍有直接脚本式导入（如 `from sectionB_load`、`from textlayer_build`），包导入与直接运行的边界不统一。
- 当前测试集中覆盖定位、意图、状态/轨迹、结构化读取与降级，未看到离线题库构建的测试。
- `Service._process()` 每轮重新构造 `Find_Intent`；追问时又构造 `rewrite_intent`，解释时再构造 `AnswerGeneration`。这会重复初始化模型客户端/链，且一次追问可能产生意图、改写、回答三次模型调用。
- 追问改写结果不参与题目定位，只作为最终讲解问题传给模型；当前证据本身已带完整题目定位，因此独立 rewriter 很可能可以直接删除，减少一次调用和一套 prompt。
- `paper.json_load()` 同时承担“在线读取缓存”和“缓存缺失时解析 PDF、写缓存”。服务查询路径因此会做昂贵写操作，职责混合，也产生并发写同一 JSON 的风险。更稳的底层边界是：离线构建缓存，在线只读缓存。
- `structured.py` 通过修改 `sys.path` 并顶层导入 `paper_parser`，注释明确是为了兼容两种运行方式；`paper_parser.paper` 也保留旧类名。这与“不保留向后兼容路径”的当前要求冲突。
- `LocationTable.FIELDS` 仍保留 `option/paragraph/word`，但当前定位器、服务和数据访问链没有写入这些字段；它们主要服务已不必要的改写器。
- `generation.py` 仍保留旧的 `peckage()/generate()` 文档检索入口，而当前产品只调用 `generate_structured()`；属于上一版向量 RAG 遗留面。
- 题库缓存已有明确 JSON schema，当前在线检索本质是确定性主键查询，不需要 RAPTOR、GraphRAG 或向量库。
- 全部 29 个现有测试通过；唯一警告是 `langchain_community.document_loaders.PyMuPDFLoader` 所在包已进入 sunset，说明离线 PDF 读取应直接使用项目已经依赖的 PyMuPDF，而不是继续经 LangChain loader 绕一层。
- `reading/paddle_ocr.py` 构造了 Bearer Authorization，且先前审查已确认令牌硬编码在源码中；这是最高优先级安全问题：立即轮换旧令牌，并只从环境变量读取。
- 38 份 `parsed_papers/*.json` 已存在，进一步支持“构建期生成、运行期只读”的边界。
- 测试大量手工修改 `sys.path`，产品模块也重复做同样操作；缺少可安装项目配置是其根因之一。
- 当前测试把意图分类器整体替换为 `FakeFindIntent`，可以验证状态机，却不能测到真实 prompt/模型是否把跳题与追问分对。需要少量固定语料的路由评测，而不是更多 mock 单测。
- Git 仓库实际根目录在上一级 `langchain/`；一次 Git 查询因 safe-directory 指向子目录而失败，后续应以父仓库为准。
- 父 Git 仓库尚无任何 commit，因此当前项目没有可用的版本历史或删除恢复能力；这是可维护性风险，且会削弱“知识更新像 PR”设想的基础。
- 当前环境版本可读取，但项目没有把它们固化：LangChain 1.3.14、core 1.5.0、community 0.4.2、langchain-deepseek 1.1.0、PyMuPDF 1.28.0、Pydantic 2.13.4、pytest 9.1.1。
- `reading/paddle_ocr.py` 的 TOKEN 确实是源码常量，不是环境变量；源码检查时已隐藏具体值。即使尚未 commit，也应视为已泄露并轮换。
- 包级导入实测：`reading.sectionA_load`、`reading.sectionC_load`、`reading.translation`、`mask.build_papers` 全部因同目录顶层导入失败；这不是风格问题，而是当前离线构建模块无法被正常 import。
- 38 份缓存数据全量校验通过基本一致性：33 份各有 10 道 Section B、答案完整且答案段存在；另外 5 份恰好是业务名单中的重复套，Section B 为 0。说明重复名单可由数据构建元数据表达，长期不宜硬编码在在线 service。
- 离线链存在两个 Section B 解析器：`retrieval/paper_parser.py` 与 `reading/sectionB_load.py`；后者还被 A/C/写作/翻译脚本继承。两套解析和两套缓存写法会漂移，应只保留一个共享解析核心。
- A、C、写作、翻译脚本分别对同一个 JSON 做“读整个文件 → 改一个键 → 重写整个文件”，既没有统一 schema 校验，也不是原子写。正确边界应是单个 builder 汇总各 parser 结果、验证后一次性写临时文件再 replace。
- `writing.py` 定义了作文锚点 `begins with the sentence`，但实际正则直接取整卷第一个引号内容，没有使用锚点；当前缓存样本看起来合理，但实现有潜在误取风险且没有单测。
- 现有 38 份 JSON 已经包含远超在线能力的数据：全部有 writing/translation，32 份有 section_a/section_c；下一层产品能力应优先读取这些结构化字段，而不是先增加向量检索或 Agent 工具。
- `mask/build_papers.py` 文档宣称目录在项目根，但代码的 `BASE_DIR` 指向 `mask/`，导致 PDF/CACHE 路径错误；同时其同目录 import 也已实测失败。离线构建入口目前实际上不可用。

## 外部项目

- Haystack 官方文档明确区分 indexing pipeline 与 query pipeline；这直接支持把 PDF/OCR/JSON 构建移出在线 `load_set()`。
- LangGraph 官方路由示例使用带 schema 的 structured output 作为路由决策，并把状态、节点和边分开；可以借“显式状态 + 受限路由值”的模式，但你的当前链路只有一个主要分支，不值得引入整套 LangGraph。
- OpenAI 官方 structured-output 示例把多轮助手中的模型输出约束为可验证结构；这比“提示模型输出 JSON，再用宽松归一化兜底”可靠。
- Rasa 的成熟对话状态模式是：每轮先抽取/验证 slot，再只允许受限事件更新 tracker；你的“locator 清洗 + RESET/PATCH/NOOP”方向正确，没必要换框架，只需把字段和更新规则收紧。
- OpenAI 的评测飞轮强调先收集失败样本、打标签、建基线再改 prompt；这适合你的意图路由，优先级高于继续加意图类别或 Agent 节点。
- GitHub 上直接叫 AI Tutor 的项目多数规模小、功能面宽，常叠加 LangGraph、多 Agent、向量库和前后端；它们更适合当反例/功能参考，不能凭仓库名当成熟架构照抄。
- 与本项目最接近的公开 exam-bank 项目采用“确定性题库/SQL 优先，只有缺题时才生成”的分层策略；它验证了已知题目与答案不应先走语义向量搜索。
- 较完整的开源考试助手也保留完全离线、确定性的运行模式和 gold QA 评测；值得借的是评测集与确定性兜底，不是其多 Agent/GraphRAG 规模。
- `echo-kaoyan-english-skill` 的 Agentic 性不来自向量检索或让模型决定答案，而来自“Agent 根据用户任务，按需读取索引、最小题型文件、rubric/strategy，并调用保存练习、记录答题、复盘错题等确定性脚本”。
- 该项目把 `SKILL.md` 定位为 router/execution coordinator：先识别考试类型与任务类型，再直接查 `index.json`，只加载一个题型规则和最小相关材料；缺失时才逐级回退到 corpus/year maps。
- 其答案安全边界与本项目目标一致：客观答案来自 `answers.json`；用户答案冲突时先声明索引答案；Echo 生成的补充内容必须标为非官方。
- 这说明“结构化题库 + Agentic 调度”完全不冲突。应修正之前结论：不建议的是让 Agent 自由决定题目定位、标准答案或任意检索路径；建议的是让 Agent 在受限工具集上主动选择下一步。
- 其 `index.json` 把每道题直接映射到稳定 id、exam、year、section、question、path 和可选 answer；Agent 做的是选择并读取最小资源，答案事实仍由索引提供。
- 与本项目相比，它真正多出来的 Agentic 闭环是：按任务加载不同 rubric、生成练习后运行校验脚本、保存练习/答题记录、主动读取错题并复盘。你的项目目前只有“讲题”一步，所以看起来更像固定流水线。
- GitHub 页面暂时无法抓取四个具体脚本内容（cache miss）；现有判断基于仓库 README、完整 SKILL 路由规则和可读取的 index.json，而不假装已经审过脚本实现。
- 后续已临时克隆仓库并读到脚本实现：它没有自建 LLM API/agent loop，Agent 能力来自 Codex/Claude Code 宿主；仓库自身提供的是路由规则、渐进式资料和可调用的确定性 CLI 工具。
- `search_papers.py` 先查派生 `index.json`，缺失才回退到 `question-map.json + answers.json`；`build_index.py` 从源数据重建索引。模式可借，但你的当前要求是不保留兼容回退，因此应只保留一种正式索引路径。
- `record_practice.py` 保存的是学生练习记录（题目、用户答案、标准答案、解析），`review_mistakes.py` 用代码比较答案；这和调试用 execution trace 是两类数据。你的 `Episode` 不应同时承担学习记忆。
- `validate_response_contract.py` 只检查标题存在；策略文档也明确说明它不能验证证据准确性、干扰项分析或教学质量。可借输出闸门，但不能把它当正确性验证器。
- 仓库测试在当前临时环境中 9 项通过，DOCX 导入测试因未安装 `python-docx` 无法加载；仓库 `requirements.txt` 已明确声明该依赖。这不是其代码测试失败，但说明复现依赖清单的重要性。
- Echo 项目不解决独立应用的多轮跳题状态：宿主 Agent 天然拥有会话上下文和文件工具。你的项目作为面向学生的独立应用，保留 `LocationTable + target resolver + trace` 是合理的额外复杂度。

## 结论候选

- 第一优先级不是增加 Agent 能力，而是把工程底座变成可安装、可构建、可复现、无密钥的项目。
- 在线服务应该只做：解析本轮定位 → 受限更新状态 → JSON 主键读取 → 必要时一次 LLM 讲解 → 写轨迹。
- 离线脚本应该独立做：PDF/OCR → 校验 → 原子写 JSON；失败不能在用户问答时临时触发。
- 轨迹缺少最终 `response`、模型/提示版本和知识版本，因此目前能审计“走了哪条分支”，还不能完整复现“当时给学生看了什么、依据哪个版本”。
- 最小目标架构：规则定位与状态机（代码）→ JSON 只读查询（代码）→ 官方答案由代码锁定 → 只有讲解文本调用一次 LLM → JSONL 记录输入、决策、证据键、输出与版本。
- 修正后的边界：当前可以做“受限工具智能体”，但不做自由 Agentic Retrieval。代码先确定并验证题目目标，Agent 只在与该目标绑定的少量只读工具中选择下一步；官方答案始终来自 JSON 索引。
- Agentic 不等于多 Agent，也不等于向量检索。当前最小闭环只需要一个讲题 Agent、两个起步工具（读取当前题、读取当前题型讲解规则）和最大工具调用次数。
- 最适合当前代码的层次是：`目标解析/状态机（代码） -> ResolvedTarget（代码校验） -> 按任务开放工具 -> 单 Agent 有界循环 -> 答案闸门 -> 轨迹`。
- 工具应与已验证目标绑定，例如 `lookup_current_question()` 不接收模型自由填写的年份和题号，而是从本轮上下文读取当前目标。这样 Agent 能决定“要不要查题、要不要加载讲解规则”，却不能偷偷换题。
- Echo 值得借的是“宿主 Agent + 明确路由 + 渐进式加载 + 确定性工具”；不应照搬其宿主假设。独立应用仍需保留自己的会话状态、跳题判断和权限边界。
- 第一版不需要 LangGraph、自写 ReAct 循环、GraphRAG、RAPTOR 或记忆框架；现有 LangChain 的 Agent 工厂足以执行模型/工具循环，等真实工具数量和分支增长后再评估图编排。
- 现有实现可直接作为 Agent 前置护栏：`parse_conditions/sanitize_position`、`state_op_of`、`LocationTable`、`structured.py` 的答案读取和 `Episode` 均应保留。
- 最小改造点只在讲解分支：删除独立 `rewrite_intent` 调用，把当前 `AnswerGeneration.generate_structured()` 的一次固定生成替换为单 Agent 的有界工具调用；纯答案分支继续直接返回 JSON 中的 KEYS。
- 第一版无需额外设计 `ResolvedTarget` 类，`Service` 当前改表后的 `effective` 字典已经能承担目标对象；等字段约束确实变复杂时再引入 Pydantic 类型。
- Agent 工具优先包装现有纯函数，并与当前 `effective` 目标绑定。新增最多一个 `tools.py`；不应复制 `structured.py` 的读取逻辑。
- 为了审计 Agent 行为，轨迹只需小幅增加最终回答和工具调用列表；学生错题/作答仍另建学习记录，不能混进运行轨迹。
- Claude 复核指出一个成立的当前 bug：追问改写文本不仅用于日志，还进入 `wants_explanation`、字母提取和讲解模型，可能改变用户真实问题。删除 rewriter 应被视为修复输入污染，而不是 Agent 化的前置重构。
- 当前只上线段落匹配讲解，命中后只有一条 `build_evidence -> generate_structured` 路径；此时引入工具 Agent 没有真实分支可选，成本高于收益。Agentic 应延后到至少存在阅读/作文/翻译/历史错题等两个以上真实动作时再评测。
- 不能从“当前不该 Agent 化”推出“真题场景永远不需要 Agent”。未来混合题型、评分、错题复盘和主动补证据都可能成为合理工具选择；正确结论是推迟，而不是永久限定到库外通用问答。
- Claude 建议保留删除后的 `FakeRewriter` 作为证伪替身不应采纳：它会保留废弃概念并让测试误导。应删除 fake 和全部 patch，另用捕获传入讲解层参数的测试证明用户原话未被改写。
- Claude 关于 `deepseek-v4-flash` 工具调用必须关闭思考模式的论据目前无法由仓库验证：其引用的 `core/find_intent.py` 在当前项目不存在；是否支持工具调用应在未来接 Agent 前做最小真实 API 兼容性实验。
- `rewritten_query` 在 rewriter 删除后与 `query` 重复，应从新轨迹 schema 删除；不为旧 JSONL 增加迁移或兼容层。
- 沙箱外使用项目解释器实测当前基线为 29 passed、1 warning，不是 30 passed；警告仍来自 `langchain-community` sunset。
- 父目录 `../core/find_intent.py` 确实存在关于 DeepSeek 思考模式与 `tool_choice` 组合的历史注释；先前只搜索项目子目录而称文件不存在是事实错误。但注释仍不能代替未来的最小真实 API 验证。
- 相对移动指令存在静默串题风险：`去年那套的44题` 只会解析出题号，现有状态机可能 PATCH 当前卷。该问题现在已经存在，并非删除 rewriter 后才出现；rewriter 从未更新定位表。
- 相对指代第一版不应自行换算：`去年` 只能给出年份，月份/套数仍不明确；`上一套/上一题` 还涉及边界和数据缺失。最小安全做法是识别移动词并明确要求完整定位。`这题/这套/那B呢` 等当前目标追问继续允许继承。
- DeepSeek 建议让 `rewritten_query` 永久保留 null 是兼容层思路，与用户已明确的“不保留向后兼容、删除废弃路径”冲突。当前无统计消费者，应该删除该键；旧 JSONL 保持原样，不做迁移。
- “死代码另开一轮清理”可采纳为施工隔离，但最终仍应删除，不能以“比翻 Git 快”为由长期保留废弃实现。
- DeepSeek 后续复核确认 `rewritten_query` 无读取方，同意直接删除；同步把 Episode 注释改成“同一 schema 版本内键集固定，旧日志不迁移”，避免跨历史文件的错误承诺。
- 相对指代守卫采用独立 `stage=ambiguous_reference`，但 `state_op` 应记录 `NOOP` 而不是 `None`：前者表示安全策略明确决定不改状态，后者会让审计者无法区分“未执行决策”和“漏记”。无需增加第四种 StateOp。
- 数字锚点优先的严格含义是：本轮实际解析到四位 `year + month + exam_set` 才绕过相对词守卫；`今年12月第1套` 仍缺数字年份，既然第一版不做换算，就必须反问。
- 删除 rewriter 时，除 Python import/patch 外还必须更新 `代码结构图.md`。已完成的 L3 施工计划不应重写历史，可在顶部加“旧方案/禁止复制 rewriter 片段”的醒目标记。
- Agent 触发条件再收紧：候选路径不仅要由代码无法可靠预判，还必须产出不同类型的教学结果；同一路径多挂一个可选读取工具不构成 Agent 化理由。
- 组合输入暴露现有 locator bug：题号正则会把“下一题/上一题”中的“一题”误识别为 `question_number=1`。不能只靠 service 守卫掩盖，必须同时在题号解析正则中排除上下/前后移动词，并加入纯函数测试。
- DeepSeek 提议的按维度放行表仍有一处错误：`第1套的下一套` 中显式套数是移动基准，不是目标；当前未实现换算时仍必须拦截。最终策略：`今年/去年/前年` 仅在同句已有四位数字年份时可忽略；上一/下一套、上一/下一题（含前一/后一变体）一律拦截。
- 更稳的实现顺序是先修正 `parse_conditions` 不再产生假题号，再解析 position，最后由 locator 纯函数根据原话与 position 判断是否存在不安全相对指代。这样无需为避免假字段而把守卫硬塞在解析前，同时能处理一条话中多个相对词。
- 相对指代早退轨迹：`state_op=NOOP`、独立 `stage=ambiguous_reference`、`hit=False`、`out_of_library=False`、`filters` 保留当前有效表且明确注明“filters 不代表本轮已检索”。
- 用户决定按秋招项目收口：不实现相对时间/相对题号守卫，把它记录为第一版已知限制。当前优先做纯删除性质的 rewriter 清理，暂不扩大状态机与 stage 契约。
- 安全复核：Git 根在父目录 `langchain/`；根 `.env` 状态为 `AM` 且已存在 index entry，仓库尚无 HEAD。必须在首次提交前从索引移除并由根 `.gitignore` 忽略。
- 根 `.gitignore` 工作区不存在但索引中有旧版本（状态 `AD`），旧内容只忽略三个中文目录；`exam-tutor/.gitignore` 虽存在，却无法匹配父目录 `.env`。
- `reading/paddle_ocr.py` 仍含硬编码 TOKEN，且不读取 `PADDLE_OCR_TOKEN`。应先在服务端轮换旧令牌，再改为环境变量；仅改源码不能使已暴露凭据失效。
- 不应直接照抄把 `parsed_papers/` 加入 ignore：当前线上服务依赖它，离线 builder 又尚不可复现。发布策略应另定（版本化合法数据、提供小型 demo 数据或先修 builder），否则克隆项目无法运行。
- DeepSeek 实施结果经独立验证：全量测试 31 passed、1 warning，关键文件 py_compile 通过；新仓库 index 不含 `.env`、databases、episodes、pyc 或明显字面量密钥，parsed_papers 共 38 份。
- 新的 `exam-tutor/.git` 嵌套在父 `langchain/.git` 内；父仓库仍显示 `.env` 和整个 `exam-tutor/` 未跟踪。若保留嵌套仓库，父根 `.gitignore` 至少必须忽略二者，否则父目录 `git add -A` 会再次制造风险。
- 新仓库暂存了 `.planning/` 三份内部笔记和 794 行历史施工计划；不适合作为公开秋招项目内容。保留 `代码结构图.md`，内部笔记和过时施工计划应从 index 移除并本地忽略。
- 新仓库缺少 README、依赖清单、`.env.example`；且当前 `.env.*` 规则会误忽略 `.env.example`，需要 `!.env.example`。这些公开可复现性工作优先于继续扩充评测集。
- `paddle_ocr.py` 已惰性读取环境变量，但错误文案声称“旧令牌已作废”，与实际尚未在服务端轮换冲突；应改为条件性提醒。Authorization scheme 建议使用惯例拼写 `Bearer`。
- `git diff --cached --check` 发现 11 处尾随空格；大多是旧文件，但首次提交前应机械清理，避免首个基线自带格式噪声。
