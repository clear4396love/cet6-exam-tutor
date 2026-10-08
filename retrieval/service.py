"""问答入口：确定性题目定位 + 代码状态机 + 每轮 JSONL 轨迹。"""
import os  # 计算项目根路径。
import sys  # 直接运行文件时补 sys.path。
import time  # 计算每轮毫秒级耗时。
import traceback  # 异常时打印完整堆栈，便于排查。
import uuid
from pathlib import Path

# 先补项目根，再导入项目内模块。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

from config import ragconfig
from memory.episode import Episode
from memory.learning_record import LearningRecord
from memory.session import LocationTable
from retrieval.generation import AnswerGeneration
from retrieval.answer_contract import conflicting_answer_claim, valid_explanation
from retrieval.draft_practice import DraftReviewer, get_draft_task, validate_feedback
from retrieval.intent import Find_Intent, state_op_of
from retrieval.practice import get_practice_item, grade_attempt, summarize_attempts, summarize_learning
from retrieval.locator import (
    parse_conditions,
    sanitize_position,
    unsafe_relative_references,
)
from retrieval.structured import (
    build_evidence,
    build_section_c_evidence,
    clean_text,
    extract_mention_letter,
    get_answer,
    get_paragraphs,
    get_question,
    get_questions,
    get_section_a_answer,
    get_section_c_question,
    load_set,
    load_set_cached_only,
    qtype_of,
    wants_explanation,
)

load_dotenv()


# 生成 prompt 约定的“证据不足”原句。
_EMPTY_HINT = "证据里没有相关内容"

# ★ L3 降级契约:所有“没定位到原题”的出口,首行统一带这个标记。
# 它是给用户看的“不伪装”信号,也是 tests/test_degrade.py 的断言锚点。
_DEGRADE_PREFIX = "【未定位到原题】"

# ★ 能力边界 ≠ 定位失败:题型/板块根本没上线,不能谎称“没找到原题”。
_UNSUPPORTED_PREFIX = "【当前题型未支持】"

# ★ 第三个前缀:重复题**不属于“未定位到原题”** —— 原题在库里,只是记在同场次另一套名下。
# 既然拆了独立 stage,横幅也必须独立,否则轨迹分得开、界面分不开。
_DUPLICATE_PREFIX = "【重复阅读题未单独收录】"

# 这 5 套的题目与同场次另一套完全重合,有意未重复录入(见 §2)。
# 这是**业务规则,不是测试数据** —— 独立成一条,因为补救动作与“异常空 B 段”不同:
# 重复套 → 去查首次出现的那套;异常套 → 查解析器。
_SKIPPED_DUPLICATE_SECTION_B = {
    (2022, 6, 3),
    (2022, 9, 2),
    (2022, 9, 3),
    (2023, 3, 2),
    (2023, 3, 3),
}

# 说了板块、且该板块整块没上线。reading 不在内 —— 36~45 本来就属于 reading。
# 值是**完整功能名**,模板直接拼“还没上线”,不在外面再挂“讲解”两个字。
_UNSUPPORTED_SECTIONS = {
    "listening": "听力讲解",
    "writing": "作文/写作讲解",
    "keys": "整套答案查询",
}

# qtype_of() 返回的英文键 → 给用户看的中文题型名。
# ★ 这个映射 structured.py 里没有,是 service 层的展示用词,别去那边找。
# 不在表里的键(含 qtype_of 返回的 None,如第20题/第56题)由调用处的 .get 兜底。
_QTYPE_NAMES = {
    "fill_blank": "选词填空(第26~35题)",
    "paragraph_matching": "段落匹配(第36~45题)",
    "multiple_choice": "仔细阅读(第46~55题)",
}




class Service:
    def __init__(self, config: ragconfig, session_id: str | None = None,
                 learning_path: Path | None = None, cached_only: bool = False):
        self.config = config  
        self.table = LocationTable()  
        self.episode = Episode(session_id=session_id)  
        self.learning_record = LearningRecord(learning_path)
        self.cached_only = cached_only
        self._tr = {}  

    def practice_question(self, year: int, month: int, exam_set: int, question_number: int) -> dict | None:
        """Read a cached practice item without exposing its answer or changing chat location."""
        cached = load_set_cached_only(year, month, exam_set)
        return get_practice_item(cached, question_number) if cached else None

    def submit_practice_answer(
        self, year: int, month: int, exam_set: int, question_number: int, submitted_answer: str,
    ) -> dict | None:
        """Grade one explicit submission and append one independent attempt event."""
        cached = load_set_cached_only(year, month, exam_set)
        result = grade_attempt(cached, question_number, submitted_answer) if cached else None
        if result is None:
            return None
        row = self.episode.record(
            stage="attempt_correct" if result["correct"] else "attempt_wrong",
            state_op="NOOP",
            table_before=self.table.to_dict(),
            filters={"year": year, "month": month, "exam_set": exam_set, "question_number": question_number},
            retrieved_doc_ids=[f"{year}_{month}_{exam_set}"],
            hit=True,
            out_of_library=False,
            answer_keys=result["answer"],
            attempt_answer=result["submitted"],
            attempt_correct=result["correct"],
        )
        saved_event_id = None
        try:
            saved_event_id = self.learning_record.append({
                "kind": "reading_attempt", "section": "reading",
                "filters": {"year": year, "month": month, "exam_set": exam_set,
                            "question_number": question_number},
                "stage": row["stage"], "attempt_answer": result["submitted"],
                "attempt_correct": result["correct"],
            })["event_id"]
        except (OSError, ValueError) as exc:
            print(f"学习记录写入失败:{exc!r}")
        return {**result, "trace_id": row["trace_id"],
                "saved": saved_event_id is not None, "event_id": saved_event_id}

    def practice_progress(self) -> dict:
        """Compute reading progress from durable answer submissions."""
        events, warnings = self.learning_record.read()
        return {**summarize_attempts(events), "history_warnings": warnings}

    def learning_progress(self, preferred_section: str | None = None) -> dict:
        """One durable read for all three practice sections."""
        events, warnings = self.learning_record.read()
        summary = summarize_learning(events, preferred_section)
        target = summary["next_action_target"]
        if target and "question_number" in target:
            cached = load_set_cached_only(target["year"], target["month"], target["exam_set"])
            if not cached or get_practice_item(cached, target["question_number"]) is None:
                summary["next_action"] = "选择另一套已收录的阅读题，先提交一次答案。"
                summary["next_action_target"] = None
        return {**summary, "history_warnings": warnings}

    def draft_question(self, year: int, month: int, exam_set: int, section: str) -> dict | None:
        """Return a verified task without cached sample answers."""
        cached = load_set_cached_only(year, month, exam_set)
        return get_draft_task(cached, section) if cached else None

    def reference_material(self, year: int, month: int, exam_set: int,
                           section: str, expected_task_text: str) -> dict:
        """Read an explicitly reviewed cache entry for a matching writing task."""
        if section not in {"writing", "translation"}:
            return {"status": "missing"}
        paper = load_set_cached_only(year, month, exam_set)
        if paper is None:
            return {"status": "missing"}
        if paper.get(f"{section}_needs_review") is not False:
            return {"status": "pending_review"}
        task = get_draft_task(paper, section)
        if task is None:
            return {"status": "missing"}
        if not isinstance(expected_task_text, str) or " ".join(task["task_text"].split()) != " ".join(expected_task_text.split()):
            return {"status": "task_mismatch"}
        sample, analysis = paper.get(f"{section}_sample"), paper.get(f"{section}_analysis")
        if not all(isinstance(value, str) and value.strip() for value in (sample, analysis)):
            return {"status": "missing"}
        return {"status": "ready", "sample": sample.strip(), "analysis": analysis.strip()}

    def submit_draft(self, year: int, month: int, exam_set: int, section: str,
                     text: str, revision_of: str | None = None,
                     submission_id: str | None = None) -> dict:
        """Save one explicit student draft; never call the model before saving."""
        task = self.draft_question(year, month, exam_set, section)
        if task is None:
            return {"status": "unavailable"}
        if not isinstance(text, str) or not text.strip() or len(text) > 10_000:
            return {"status": "invalid"}
        if submission_id is not None and (not isinstance(submission_id, str) or not submission_id):
            return {"status": "invalid"}
        filters = {"year": year, "month": month, "exam_set": exam_set}
        if revision_of is not None:
            drafts, _ = self.learning_record.read()
            if not any(row["kind"] == "draft_submitted" and row["draft_id"] == revision_of
                       and row["section"] == section and row["filters"] == filters for row in drafts):
                return {"status": "invalid"}
        try:
            saved = self.learning_record.append({
                "kind": "draft_submitted", "section": section, "filters": filters,
                "draft_text": text, "task_text": task["task_text"],
                "review_scope": task["review_scope"], "revision_of": revision_of,
                "submission_id": submission_id or uuid.uuid4().hex,
            })
        except OSError as exc:
            return {"status": "save_error", "message": str(exc)}
        except ValueError:
            return {"status": "invalid"}
        if saved["draft_text"] != text or saved["filters"] != filters or saved["section"] != section:
            return {"status": "invalid"}
        return {"status": "saved", "draft_id": saved["draft_id"]}

    def review_draft(self, draft_id: str) -> dict:
        """Review a saved draft once; failure leaves the draft retryable."""
        rows, warnings = self.learning_record.read()
        draft = next((row for row in rows if row["kind"] == "draft_submitted"
                      and row["draft_id"] == draft_id), None)
        if draft is None:
            return {"status": "not_found", "history_warnings": warnings}
        existing = next((row for row in rows if row["kind"] == "feedback_ready"
                         and row["draft_id"] == draft_id), None)
        if existing:
            return {"status": "ready", "feedback": existing["feedback"], "warning": ""}
        try:
            raw = DraftReviewer(self.config).generate(
                draft["section"], draft["task_text"], draft["draft_text"], draft["review_scope"])
            feedback = validate_feedback(raw, draft["section"], draft["draft_text"],
                                         draft["task_text"], draft["review_scope"])
        except Exception as exc:
            print(f"主观题评阅失败:{type(exc).__name__}")
            return {"status": "pending"}
        if feedback is None:
            return {"status": "pending"}
        warning = ("部分引文无法在原文中核实，评语可能不完整。"
                   if len(raw["issues"]) != len(feedback["issues"]) else "")
        try:
            saved = self.learning_record.append({
                "kind": "feedback_ready", "section": draft["section"], "filters": draft["filters"],
                "draft_id": draft_id, "feedback": feedback,
            })
        except (OSError, ValueError):
            return {"status": "feedback_not_saved", "feedback": feedback, "warning": warning}
        return {"status": "ready", "feedback": saved["feedback"], "warning": warning}

    def draft_history(self, section: str | None = None) -> list[dict]:
        """Restore submitted originals, revisions, and adopted feedback in file order."""
        rows, _ = self.learning_record.read()
        feedback = {row["draft_id"]: row["feedback"] for row in rows
                    if row["kind"] == "feedback_ready"}
        return [
            {key: row[key] for key in ("draft_id", "section", "filters", "ts", "draft_text",
                                         "task_text", "review_scope", "revision_of")}
            | {"feedback": feedback.get(row["draft_id"])}
            for row in rows if row["kind"] == "draft_submitted"
            and (section is None or row["section"] == section)
        ]

    def practice_feedback(self, attempt_trace_id: str) -> str:
        """Explain one completed attempt; model failure never changes its grade."""
        row = next((event for event in self.episode.lines()
                    if event.get("trace_id") == attempt_trace_id
                    and event.get("stage") in {"attempt_correct", "attempt_wrong"}), None)
        if row is None:
            return "找不到这次作答记录，不能生成解析。"
        progress = self.practice_progress()
        tier = progress["tier"]
        fallback = (
            "本次作答记录还少，先核对题干关键词与答案段落，再尝试下一题。" if tier == "plan_insufficient_data"
            else "先对照本题证据复盘，再做一道题检验思路。" if tier == "weakness_snapshot"
            else "先复习本次做错的题，再选一道题检验是否改进。"
        )
        filters = row.get("filters")
        if not isinstance(filters, dict) or not all(
            isinstance(filters.get(key), int) for key in ("year", "month", "exam_set", "question_number")
        ):
            return fallback
        cached = load_set_cached_only(filters["year"], filters["month"], filters["exam_set"])
        if not cached:
            return fallback
        result = grade_attempt(cached, filters["question_number"], row.get("attempt_answer"))
        if result is None or result["answer"] != row.get("answer_keys") or result["correct"] != row.get("attempt_correct"):
            return fallback
        if 26 <= filters["question_number"] <= 35:
            status = "答对了" if result["correct"] else "这次没答对"
            return (
                f"{status}。第{filters['question_number']}空的 KEYS 答案是 "
                f"{result['answer']}（{result['answer_word']}）。"
                "建议对照空位前后的语法和搭配再检查一遍；这不是官方语法解析。"
            )
        if 46 <= filters["question_number"] <= 55:
            fixed = (f"{'答对了' if result['correct'] else '这次没答对'}。"
                     f"第{filters['question_number']}题标准答案是 {result['answer']}。")
            unavailable = fixed + "参考解析（非官方）：解析暂不可用；请回到本题原文核对题干关键词，再试下一题。"
            evidence = build_section_c_evidence(cached, filters["question_number"])
            if not evidence:
                return unavailable
            try:
                output = AnswerGeneration(self.config).generate_section_c_practice_feedback(evidence, result, progress)
            except Exception as exc:
                print(f"仔细阅读练习反馈生成失败:{exc!r}")
                return unavailable
            if not isinstance(output, str) or not output.strip():
                return unavailable
            if conflicting_answer_claim(output, result["answer"]):
                return unavailable
            return fixed + "参考解析（非官方）：" + output.strip()
        evidence = build_evidence(cached, filters["question_number"], result["submitted"])
        try:
            output = AnswerGeneration(self.config).generate_practice_feedback(evidence, result, progress)
        except Exception as exc:
            print(f"练习反馈生成失败:{exc!r}")
            return fallback
        if not isinstance(output, str) or not output.strip():
            return fallback
        if conflicting_answer_claim(output, result["answer"]):
            return (f"第{filters['question_number']}题 KEYS 答案是 {result['answer']}。"
                    "参考解析暂不可用；请回到本题原文核对题干关键词。")
        return output.strip()

    def _mark(self, **fields) -> None:
        """分支插桩：只更新本轮事实，不写盘、不改变返回值。"""
        self._tr.update(fields)

    def process(self, user_message: str) -> str:
        """唯一对外入口；无论正常、早退还是异常，每轮只记录一次。"""
        started = time.perf_counter()  # 在任何模型/磁盘调用前开始计时。
        self._tr = {}  # 防止上一轮字段泄漏到这一轮。
        error = None  # 正常请求在轨迹中保持 null。
        answer = None  # 确保异常后仍有明确返回值。
        try:
            answer = self._process(user_message)
        except Exception as exc:
            error = repr(exc)
            answer = "出错了,请稍后再试"
            print(f"处理出错:{exc!r}")
            traceback.print_exc()
        finally:
            # 唯一写入点覆盖 _process 的全部早退和异常出口。
            self.episode.record(
                **{
                    **self._tr,
                    "query": user_message,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "error": error,
                }
            )
        return answer

    def _process(self, user_message: str) -> str:
        """完成意图、最终定位、状态操作和结构化回答。"""
        # LLM 只给语义意图；定位和状态写入全部由代码负责。
        intent, _, degraded = Find_Intent(self.config).merged(
            user_message, self.table
        )

        # 定位、字母提取和讲解一律基于用户原话；追问改写器已整体删除 ——
        # 它既不参与定位,又被当成"用户问题"喂给正则和讲解模型。
        raw_position = parse_conditions(user_message)
        position = sanitize_position(raw_position)

        # 翻译没有题号；明确说了 26~55 题就切回阅读，避免继承旧的翻译板块。
        if (position.get("question_number") in range(26, 56)
                and "section" not in position
                and self.table.get("section") == "translation"):
            position["section"] = "reading"

        # ★ 相对指代守卫:必须在 state_op_of / 改表 / 读题库之前拦下。
        #   "下一题""去年"的基准不唯一(可能是定位表,也可能是同句里的数字),
        #   第一版一律不换算 —— 直接反问,并让当前定位表原样不动。
        unsafe = unsafe_relative_references(user_message, position)
        if unsafe:
            current = self.table.to_dict()
            self._mark(
                intent=intent,
                state_op="NOOP",
                position=position,
                table_before=current,
                filters=current,
                stage="ambiguous_reference",
                hit=False,
                out_of_library=False,
            )
            return (
                f"“{'、'.join(unsafe)}”还不能安全换算。"
                "请直接提供四位年份、月份、套数和题号，例如：2025年12月第1套第44题。"
            )

        invalid_input = any(key not in position for key in raw_position)

        # 必须在最终 position 之后算；否则模型漏字段会导致跨卷串状态。
        state_op = state_op_of(
            intent, position, self.table, degraded=degraded
        )
        if invalid_input and state_op != "NOOP":
            state_op = "RESET"

        # 先记录改表前快照和决策直接输入，之后才执行状态操作。
        self._mark(
            intent=intent,
            state_op=state_op,
            position=position,
            table_before=self.table.to_dict(),
        )

        # 执行受限枚举操作；RESET 先清表，RESET/PATCH 再写入。
        if state_op == "RESET":
            self.table.clear()
        if state_op != "NOOP":
            self.table.update(position)

        # 有效定位就是改表后的非空字段；它也是实际回答使用的 filters。
        effective = self.table.to_dict()
        self._mark(filters=effective)

        # 闲聊和语气词同样经过状态决策，但 state_op_of 保证它们是 NOOP。
        if intent == "NOT_RELATED":
            self._mark(stage="not_related", hit=False, out_of_library=False)
            return "请问英语六级问题"
        if intent == "AMBIGUOUS":
            self._mark(stage="ambiguous", hit=False, out_of_library=False)
            return "请说一道具体的六级题目"

        # 不再保留旧的“NEW_QUESTION + 只有题号”专用反问；下层统一检查更准确。
        return self._structured_answer(effective, user_message)

    def _structured_answer(self, loc: dict, user_message: str) -> str:
        """按题型选择结构化缓存问答。

        user_message 必须是**用户原话**:它要参与"要不要讲解"的判断、字母提取
        和讲解生成。传模型改写过的句子会让正则抠出用户没提过的字母、把
        "为什么"判反,并让讲解模型看到一句不是学生说的话。

        L3a 契约:定位不到或者没上线的任何一条出口,首行都带标记,
        并用 stage 说清是哪一种,绝不伪装成真题答案。
        """
        if loc.get("section") == "translation":
            return self._translation_answer(loc, user_message)

        qnum = loc.get("question_number")
        if qnum is None:
            # 说了板块、且整块没上线 —— 能力边界,不是“没找到原题”。
            section = loc.get("section")
            if section in _UNSUPPORTED_SECTIONS:
                self._mark(stage="unsupported_type", hit=False, out_of_library=True)
                return (
                    f"{_UNSUPPORTED_PREFIX}{_UNSUPPORTED_SECTIONS[section]}还没上线;"
                    "目前支持六级阅读段落匹配题(第36~45题)的讲解,"
                    "以及仔细阅读(第46~55题)的讲解、选词填空(第26~35题)的查答案、翻译练习参考译文和逐句解析。"
                )
            # 卷已经说全、只差题号 —— 别再让用户把年月套重说一遍。
            year, month, exam_set = loc.get("year"), loc.get("month"), loc.get("exam_set")
            ask = (
                f"{year}年{month}月第{exam_set}套的哪一道题?"
                "阅读部分有第26~35题(选词填空)、第36~45题(段落匹配)和第46~55题(仔细阅读)。"
                if year and month and exam_set
                else "请说清是哪年哪月第几套的哪道题,比如:2024年12月第1套 第45题为什么选O。"
            )
            self._mark(stage="missing_question", hit=False, out_of_library=False)
            return (
                f"{_DEGRADE_PREFIX}我目前上线了六级阅读段落匹配题(第36~45题)的讲解,"
                "以及仔细阅读(第46~55题)的讲解、选词填空(第26~35题)的查答案。" + ask
            )

        # Section B/C 可讲解;Section A 只按缓存查答案。
        qtype = qtype_of(qnum)
        if qtype == "fill_blank":
            return self._fill_blank_answer(loc, qnum, user_message)
        if qtype == "multiple_choice":
            return self._multiple_choice_answer(loc, qnum, user_message)
        if qtype != "paragraph_matching":
            self._mark(stage="unsupported_type", hit=False, out_of_library=True)
            qtype_name = _QTYPE_NAMES.get(qtype, "未支持题型")
            return (
                f"{_UNSUPPORTED_PREFIX}第{qnum}题属于{qtype_name},该题型的解析还没上线;"
                "目前支持段落匹配题 36~45、仔细阅读 46~55 的讲解,以及选词填空 26~35 的查答案。"
            )

        # 年、月、套缺一不可;题号继承不等于允许猜卷。
        year = loc.get("year")
        month = loc.get("month")
        exam_set = loc.get("exam_set")
        if not (year and month and exam_set):
            self._mark(stage="missing_paper", hit=False, out_of_library=False)
            return (
                f"{_DEGRADE_PREFIX}第{qnum}题我知道了,但卷子还不全。"
                "这道题是哪年哪月第几套的?告诉我年份、月份和套数,我能答得更准。"
            )

        # ★ 已知有意跳过的重复套(5 套,见 §2):不映射、不猜,直接说明。
        # 位置必须在这儿 —— 在 section 检查和年月套确认**之后**、load_set **之前**:
        #   放在最顶端会把「2022年6月第3套作文怎么写」也回成“段落匹配题重复”,又是答非所问。
        #   首次出现的那一套未必是第 1 套,所以文案不点名具体套数。
        #   提前 return 意味着**不碰缓存也不碰 PDF**,零磁盘读写。
        if (year, month, exam_set) in _SKIPPED_DUPLICATE_SECTION_B:
            self._mark(stage="duplicate_section", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DUPLICATE_PREFIX}这套的段落匹配题与同场次其他套重复,没有单独收录。"
                "请查询它首次出现的套题。"
            )

        # load_set 使用确定性 year_month_set 键,不做向量搜索。
        # ★ 注意:没缓存但有文字层 PDF 时,它会解析并写盘(见计划书 §3)。
        parsed = (load_set_cached_only(year, month, exam_set) if self.cached_only
                  else load_set(year, month, exam_set))
        paper_name = f"{year}年{month}月第{exam_set}套"

        if parsed is None:
            self._mark(stage="cache_miss_paper", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}整套都还没入库,这题没有解析数据。"
                "换一套试试,或者确认套数写对没有。"
            )

        # 这套的阅读没收录,且不在已知重复名单里 —— **原因不明的空数据,是异常,要查**。
        # 这和“题号写错”也是两回事,不能混进 cache_miss_question。
        # (那 5 套已知重复的在上面就被接走了,到不了这儿。)
        questions = get_questions(parsed) or {}
        has_section_b = any(
            36 <= int(n) <= 45 for n in questions if str(n).isdigit()
        )
        if not has_section_b:
            self._mark(stage="cache_miss_section", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}的阅读部分没有收录,"
                "段落匹配题(36~45)一整节都缺,所以这题没有原文也没有答案。"
                "换一套年份或场次试试。"
            )

        question = get_question(parsed, qnum)
        if question is None:
            self._mark(stage="cache_miss_question", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}已入库,但没有第{qnum}题的题干。"
                "确认一下题号?这个板块只有第36~45题。"
            )

        answer_keys = get_answer(parsed, qnum)
        if answer_keys is None:
            self._mark(stage="cache_miss_answer", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}第{qnum}题有题干,但缺 KEYS 官方答案。"
                "答案只认 KEYS、不猜,所以这题暂时讲不了。"
            )

        # 命中的缓存键就是 v1 的 retrieved_doc_id。
        cache_key = f"{year}_{month}_{exam_set}"
        self._mark(
            hit=True,
            out_of_library=False,
            retrieved_doc_ids=[cache_key],
            answer_keys=answer_keys,
        )

        # 讲解模式允许用用户提到的字母拼证据，但本轮不把散文输出当模型答案。
        if wants_explanation(user_message):
            mention_for_evidence = extract_mention_letter(user_message)
            evidence = build_evidence(parsed, qnum, mention_for_evidence)
            generator = AnswerGeneration(self.config, max_tokens=3000)
            output = generator.generate_structured(user_message, evidence)
            # 模型偶发空返回时只重试一次。
            if not output or not output.strip():
                output = generator.generate_structured(user_message, evidence)
            if not output or not output.strip():
                self._mark(
                    stage="generation_empty",
                    answer_mentioned=None,
                    answer_agrees=None,
                )
                return "这题暂时没讲出来,换个问法再试一次(比如:为什么不选X)。"
            if _EMPTY_HINT in output:
                self._mark(
                    stage="evidence_missing",
                    answer_mentioned=None,
                    answer_agrees=None,
                )
                return "证据里没有相关内容,无法作答"
            if not valid_explanation(output, "B", answer_keys):
                self._mark(stage="generation_invalid", answer_verified=False,
                           answer_mentioned=None, answer_agrees=None)
                return f"第{qnum}题按 KEYS 选 {answer_keys}。详细解析未通过校验，暂不展示。"
            self._mark(
                stage="explanation",
                answer_verified=True,
                answer_mentioned=None,
                answer_agrees=None,
            )
            return output

        # 答案模式只解析用户明确提到的字母，不解析模型散文。
        paragraphs = get_paragraphs(parsed)
        answer_mentioned = extract_mention_letter(user_message)
        if answer_mentioned:
            # 只有用户真的提到字母时才产生 True/False；否则必须保持 null。
            answer_agrees = answer_mentioned == answer_keys
            self._mark(
                stage="answer",
                answer_mentioned=answer_mentioned,
                answer_agrees=answer_agrees,
            )
            if answer_agrees:
                return f"是的,第{qnum}题选 {answer_keys}。"
            return (
                f"KEYS 答案不是 {answer_mentioned},是 {answer_keys}。"
                f"想看它和 {answer_mentioned} 段逐项对比,可以问\"为什么不选 {answer_mentioned}\"。"
            )

        # 普通问答案没有提字母，三态字段保持 None，不能记成 False。
        self._mark(
            stage="answer",
            answer_mentioned=None,
            answer_agrees=None,
        )
        head = clean_text(paragraphs.get(answer_keys, ""))[:80]
        return f"第{qnum}题答案:{answer_keys}" + (f"({head}…)" if head else "")

    def _translation_answer(self, loc: dict, user_message: str) -> str:
        """只读已审核缓存中的练习译文和按需解析；待核内容不展示。"""
        year, month, exam_set = loc.get("year"), loc.get("month"), loc.get("exam_set")
        if not (year and month and exam_set):
            self._mark(stage="missing_paper", hit=False, out_of_library=False)
            return f"{_DEGRADE_PREFIX}请说清翻译是哪年哪月第几套，例如：2024年12月第1套翻译怎么写。"

        paper_name = f"{year}年{month}月第{exam_set}套"
        parsed = load_set_cached_only(year, month, exam_set)
        if parsed is None:
            self._mark(stage="cache_miss_paper", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return f"{_DEGRADE_PREFIX}{paper_name}还没有缓存，暂时查不到翻译。"

        # 不把待核内容或缺少审核标记的历史缓存误当成可公开的答案。
        if parsed.get("translation_needs_review") is not False:
            self._mark(stage="translation_pending_review", hit=False,
                       out_of_library=False, retrieved_doc_ids=[])
            return f"{paper_name}的翻译内容还在待核，暂不展示练习译文。"

        source, sample = parsed.get("translation"), parsed.get("translation_sample")
        if not (isinstance(source, str) and source.strip()
                and isinstance(sample, str) and sample.strip()):
            self._mark(stage="cache_miss_section", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return f"{_DEGRADE_PREFIX}{paper_name}缺少可信的翻译原文或练习译文。"

        wants_analysis = (
            wants_explanation(user_message)
            or any(
                word in user_message
                for word in ("思路", "写法", "说明", "讲解", "方法", "分析", "逐句")
            )
        )
        analysis = parsed.get("translation_analysis")
        if wants_analysis and not (isinstance(analysis, str) and analysis.strip()):
            self._mark(stage="translation_analysis_missing", hit=False,
                       out_of_library=False, retrieved_doc_ids=[f"{year}_{month}_{exam_set}"])
            return (f"**{paper_name}翻译原文**\n\n{source.strip()}\n\n"
                    f"**练习参考译文（非官方答案）**\n\n{sample.strip()}\n\n"
                    "这套题的逐句解析暂未缓存。")

        self._mark(stage="translation_analysis" if wants_analysis else "translation_sample",
                   hit=True, out_of_library=False,
                   retrieved_doc_ids=[f"{year}_{month}_{exam_set}"])
        answer = (f"**{paper_name}翻译原文**\n\n{source.strip()}\n\n"
                  f"**练习参考译文（非官方答案）**\n\n{sample.strip()}")
        if wants_analysis:
            answer += f"\n\n**逐句解析**\n\n{analysis.strip()}"
        return answer

    def _fill_blank_answer(self, loc: dict, qnum: int, user_message: str) -> str:
        """Section A 选词填空(26~35)第一版:只按缓存回报答案,不让模型改判。

        只读已有 JSON(load_set_cached_only):缺缓存不重建、不写盘。
        缺数据一律走 _DEGRADE_PREFIX,和段落匹配那条路同一套降级语;
        解释请求明确回不支持 —— 不碰 build_evidence,也不碰讲解模型
        (answer_prompt.py 那份 prompt 是写给 36~45 的,硬套会编理由)。
        """
        year, month, exam_set = loc.get("year"), loc.get("month"), loc.get("exam_set")
        if not (year and month and exam_set):
            self._mark(stage="missing_paper", hit=False, out_of_library=False)
            return (
                f"{_DEGRADE_PREFIX}第{qnum}题我知道了,但卷子还不全。"
                "这道题是哪年哪月第几套的?告诉我年份、月份和套数,我能答得更准。"
            )

        paper_name = f"{year}年{month}月第{exam_set}套"
        parsed = load_set_cached_only(year, month, exam_set)
        if parsed is None:
            self._mark(stage="cache_miss_paper", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}整套都还没入库,这题没有解析数据。"
                "换一套试试,或者确认套数写对没有。"
            )

        pair = get_section_a_answer(parsed, qnum)
        if pair is None:
            self._mark(stage="cache_miss_section", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_DEGRADE_PREFIX}{paper_name}暂时查不到第{qnum}空的答案"
                "(选词填空 26~35 没有收录,或答案和词库对不上)。换一套试试。"
            )

        # 解释请求放在数据检查之后:缺数据时别让用户以为「有答案、只是没讲解」。
        if wants_explanation(user_message):
            self._mark(stage="unsupported_type", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return (
                f"{_UNSUPPORTED_PREFIX}选词填空(第26~35题)目前只能查答案,"
                "还不能讲为什么填这个词。"
            )

        letter, word = pair
        self._mark(stage="answer", hit=True, out_of_library=False,
                   retrieved_doc_ids=[f"{year}_{month}_{exam_set}"],
                   answer_keys=letter)
        return f"第{qnum}空选 {letter},填 {word}。"

    def _multiple_choice_answer(self, loc: dict, qnum: int, user_message: str) -> str:
        """Section C 仔细阅读(46~55):从缓存查答案,有原文时可生成讲解。"""
        year, month, exam_set = loc.get("year"), loc.get("month"), loc.get("exam_set")
        if not (year and month and exam_set):
            self._mark(stage="missing_paper", hit=False, out_of_library=False)
            return (
                f"{_DEGRADE_PREFIX}第{qnum}题我知道了,但卷子还不全。"
                "请补充年份、月份和套数。"
            )

        paper_name = f"{year}年{month}月第{exam_set}套"
        parsed = load_set_cached_only(year, month, exam_set)
        if parsed is None:
            self._mark(stage="cache_miss_paper", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return f"{_DEGRADE_PREFIX}{paper_name}还没有缓存,暂时查不到第{qnum}题。"

        pair = get_section_c_question(parsed, qnum)
        if pair is None:
            self._mark(stage="cache_miss_section", hit=False, out_of_library=True,
                       retrieved_doc_ids=[])
            return f"{_DEGRADE_PREFIX}{paper_name}第{qnum}题缺少可信的仔细阅读答案或选项。"

        letter, option = pair
        self._mark(stage="answer", hit=True, out_of_library=False,
                   retrieved_doc_ids=[f"{year}_{month}_{exam_set}"],
                   answer_keys=letter)
        if wants_explanation(user_message):
            evidence = build_section_c_evidence(parsed, qnum)
            if evidence is None:
                self._mark(stage="cache_miss_section", hit=False,
                           out_of_library=True, retrieved_doc_ids=[])
                return f"{_DEGRADE_PREFIX}{paper_name}第{qnum}题缺少原文或题干,目前只能确认答案是 {letter}。"
            try:
                generator = AnswerGeneration(self.config, max_tokens=3000)
                output = generator.generate_section_c(user_message, evidence)
                if not output or not output.strip():
                    output = generator.generate_section_c(user_message, evidence)
            except Exception as exc:
                print(f"仔细阅读讲解生成失败:{exc!r}")
                self._mark(stage="generation_error")
                return f"第{qnum}题选 {letter}：{option} 详细讲解暂时无法生成,请稍后重试。"
            if not output or not output.strip():
                self._mark(stage="generation_empty")
                return f"第{qnum}题选 {letter}：{option} 详细讲解暂时没生成,请稍后重试。"
            if _EMPTY_HINT in output:
                self._mark(stage="evidence_missing")
                return f"第{qnum}题选 {letter}：{option} 现有原文不足以生成详细讲解。"
            if not valid_explanation(output, "C", letter):
                self._mark(stage="generation_invalid", answer_verified=False)
                return f"第{qnum}题按 KEYS 选 {letter}。详细解析未通过校验，暂不展示。"
            self._mark(stage="explanation", answer_verified=True)
            return output
        return f"第{qnum}题选 {letter}：{option}"


if __name__ == "__main__":
    # 一个 CLI 进程就是一个会话，所以不传 session_id 也能自然复用状态。
    service = Service(ragconfig)
    while True:
        question = input("你想问的问题是:")
        if question.strip().lower() == "q":
            print("退出问答")
            break
        print(service.process(question))
