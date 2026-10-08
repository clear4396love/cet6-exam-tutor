"""端到端场景评测(13 场景 / 18 步):真调模型,走完整 Service.process()。

测的是"真实意图识别 + 定位 + 状态机 + 降级出口 + 回包形状"这一整条链路 ——
这是现有 36 条 pytest(FakeFindIntent 替身)和 smoke_eval.py(只测讲解生成)都盖不到的部分。

★ 本模块**导入时不碰模型、不碰磁盘**:所有真实调用和写盘都在 main() 里,
  这样 tests/test_scenario_eval.py 可以安全地 import score_step / sections_present。

用法:
    python tools/scenario_eval.py            # 正式跑 13 场景,覆盖写 eval/scenario_results.jsonl
    python tools/scenario_eval.py --only 13  # 只跑 Section A 场景,只打印、不写文件
    python tools/scenario_eval.py --practice --only 1  # 离线练习场景,只打印
"""
import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ragconfig  # noqa: E402
from memory.episode import Episode  # noqa: E402
from retrieval.service import Service  # noqa: E402
from retrieval.answer_prompt import SECTION_B_HEADINGS  # noqa: E402
from retrieval.structured import get_answer, get_section_a_answer, load_set  # noqa: E402
from tools.smoke_eval import classify  # noqa: E402  解析器复用,不写第二份

OUT_PATH = os.path.join(PROJECT_ROOT, "eval", "scenario_results.jsonl")

# 八节标题的锚(第 7 节是"为什么选I",用前缀判,字母不固定)。
_SECTIONS = tuple(name.replace("[答案]", "") for name in SECTION_B_HEADINGS)

# 占位符:main() 里换成该步真实坐标的 KEYS 字母 —— 不写死,免得手抄错一个字母带偏整轮。
KEYS = "__KEYS__"

# 每步:(用户原话, 该步坐标 (年,月,套,题号) 或 None, 期望 dict)
# 坐标**只用来现取 KEYS**,不参与断言;filters 的期望是单独写死的整表。
# 期望里没写的键 = 不检查;写了 `None` = 要检查(见施工计划 §二)。
CASES = (
    {
        "id": 1,
        "name": "完整定位后回答",
        "steps": (
            ("2024年12月第1套第43题选什么", (2024, 12, 1, 43),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "filters": {"year": 2024, "month": 12, "exam_set": 1, "question_number": 43},
              "answer_keys": KEYS, "reply_answer": KEYS}),
        ),
    },
    {
        "id": 2,
        "name": "同题追问",
        "steps": (
            ("2024年12月第1套第43题选什么", (2024, 12, 1, 43),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "answer_keys": KEYS, "reply_answer": KEYS}),
            ("为什么不选A", (2024, 12, 1, 43),
             {"intent": "FOLLOW_UP", "state_op": "PATCH", "stage": "explanation",
              "answer_keys": KEYS, "reply_answer": KEYS, "sections_8": 8}),
        ),
    },
    {
        "id": 3,
        "name": "同卷换题",
        "steps": (
            ("2024年12月第1套第43题选什么", (2024, 12, 1, 43),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "answer_keys": KEYS, "reply_answer": KEYS}),
            # "那44题呢"自己带了题号 → prompt 第 39 行要求优先判 NEW_QUESTION;
            # 卷级锚点一个没给、当前卷完整 → 走"完整当前卷 + 新题号"那支 PATCH。
            ("那44题呢", (2024, 12, 1, 44),
             {"intent": "NEW_QUESTION", "state_op": "PATCH", "stage": "answer",
              "filters": {"year": 2024, "month": 12, "exam_set": 1, "question_number": 44},
              "answer_keys": KEYS, "reply_answer": KEYS}),
        ),
    },
    {
        "id": 4,
        "name": "切换试卷",
        "steps": (
            ("2024年12月第1套第43题选什么", (2024, 12, 1, 43),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "answer_keys": KEYS, "reply_answer": KEYS}),
            ("2024年12月第2套第36题选什么", (2024, 12, 2, 36),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "filters": {"year": 2024, "month": 12, "exam_set": 2, "question_number": 36},
              "answer_keys": KEYS, "reply_answer": KEYS}),
        ),
    },
    {
        "id": 5,
        "name": "质疑错误选项",
        "steps": (
            ("2024年12月第1套第43题为什么不选A", (2024, 12, 1, 43),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "explanation",
              "answer_keys": KEYS, "reply_answer": KEYS, "sections_8": 8}),
        ),
    },
    {
        "id": 6,
        "name": "相对指代拦截",
        "steps": (
            # 守卫在 state_op_of / 改表之前拦下,所以 filters 只能是空表(严格相等,不是子集)。
            ("2024年12月第1套的下一题", None,
             {"intent": "NEW_QUESTION", "state_op": "NOOP", "stage": "ambiguous_reference",
              "filters": {}, "answer_keys": None}),
        ),
    },
    {
        "id": 7,
        "name": "缺年份",
        "steps": (
            ("第43题为什么这样选", None,
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "missing_paper",
              "answer_keys": None}),
        ),
    },
    {
        "id": 8,
        "name": "缺套数",
        "steps": (
            ("2024年12月第43题选什么", None,
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "missing_paper",
              "answer_keys": None}),
        ),
    },
    {
        "id": 9,
        "name": "缺题号",
        "steps": (
            ("2024年12月第1套", None,
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "missing_question",
              "answer_keys": None}),
        ),
    },
    {
        "id": 10,
        "name": "不支持题型",
        "steps": (
            ("2024年12月第1套作文怎么写", None,
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "unsupported_type",
              "answer_keys": None}),
        ),
    },
    {
        "id": 11,
        "name": "闲聊",
        "steps": (
            ("你好呀", None,
             {"intent": "NOT_RELATED", "state_op": "NOOP", "stage": "not_related",
              "answer_keys": None}),
        ),
    },
    {
        "id": 12,
        "name": "模糊输入",
        "steps": (
            ("怎么办", None,
             {"intent": "AMBIGUOUS", "state_op": "NOOP", "stage": "ambiguous",
              "answer_keys": None}),
        ),
    },
    {
        "id": 13,
        "name": "Section A 查询与解释边界",
        "steps": (
            ("2024年12月第1套第26题填什么", (2024, 12, 1, 26),
             {"intent": "NEW_QUESTION", "state_op": "RESET", "stage": "answer",
              "filters": {"year": 2024, "month": 12, "exam_set": 1, "question_number": 26},
              "answer_keys": KEYS, "reply_answer": KEYS}),
            ("那27题呢", (2024, 12, 1, 27),
             {"intent": "NEW_QUESTION", "state_op": "PATCH", "stage": "answer",
              "filters": {"year": 2024, "month": 12, "exam_set": 1, "question_number": 27},
              "answer_keys": KEYS, "reply_answer": KEYS}),
            ("为什么填这个词？", (2024, 12, 1, 27),
             {"intent": "FOLLOW_UP", "state_op": "PATCH", "stage": "unsupported_type",
              "filters": {"year": 2024, "month": 12, "exam_set": 1, "question_number": 27},
              "answer_keys": None}),
        ),
    },
)

# Offline practice uses the existing 2024-12-1 cache (question 43 KEY=I).
# It never asks a model to determine the answer or generate a question.
PRACTICE_CASES = (
    {
        "id": 1,
        "name": "逐题判分与三档会话反馈",
        "steps": (
            {"action": "view", "coord": (2024, 12, 1, 43),
             "expect": {"item_available": True, "answer_hidden": True, "attempt_count": 0}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "A",
             "expect": {"stage": "attempt_wrong", "answer_keys": "I", "correct": False,
                        "attempt_count": 1, "tier": "plan_insufficient_data"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "I",
             "expect": {"stage": "attempt_correct", "answer_keys": "I", "correct": True,
                        "attempt_count": 2, "tier": "plan_insufficient_data"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "A",
             "expect": {"stage": "attempt_wrong", "answer_keys": "I", "correct": False,
                        "attempt_count": 3, "tier": "weakness_snapshot"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "A",
             "expect": {"stage": "attempt_wrong", "answer_keys": "I", "correct": False,
                        "attempt_count": 4, "tier": "weakness_snapshot"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "I",
             "expect": {"stage": "attempt_correct", "answer_keys": "I", "correct": True,
                        "attempt_count": 5, "tier": "weakness_snapshot"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "I",
             "expect": {"stage": "attempt_correct", "answer_keys": "I", "correct": True,
                        "attempt_count": 6, "tier": "weakness_snapshot"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "I",
             "expect": {"stage": "attempt_correct", "answer_keys": "I", "correct": True,
                        "attempt_count": 7, "tier": "weakness_snapshot"}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "I",
             "expect": {"stage": "attempt_correct", "answer_keys": "I", "correct": True,
                        "attempt_count": 8, "tier": "session_review"}},
        ),
    },
    {
        "id": 2,
        "name": "无效题号和答案不记作答",
        "steps": (
            {"action": "view", "coord": (2024, 12, 1, 35),
             "expect": {"item_available": False, "answer_hidden": True, "attempt_count": 0}},
            {"action": "submit", "coord": (2024, 12, 1, 43), "submitted": "?",
             "expect": {"stage": None, "answer_keys": None, "correct": None,
                        "attempt_count": 0, "tier": "plan_insufficient_data"}},
        ),
    },
    {
        "id": 3,
        "name": "选词填空安全出题与 KEYS 判分",
        "steps": (
            {"action": "view", "coord": (2021, 12, 1, 26),
             "expect": {"item_available": True, "answer_hidden": True, "attempt_count": 0}},
            {"action": "submit", "coord": (2021, 12, 1, 26), "submitted": "A",
             "expect": {"stage": "attempt_wrong", "answer_keys": "B", "correct": False,
                        "attempt_count": 1, "tier": "plan_insufficient_data"}},
            {"action": "submit", "coord": (2021, 12, 1, 26), "submitted": "B",
             "expect": {"stage": "attempt_correct", "answer_keys": "B", "correct": True,
                        "attempt_count": 2, "tier": "plan_insufficient_data"}},
        ),
    },
    {
        "id": 4,
        "name": "仔细阅读双篇安全出题与逐题判分",
        "steps": (
            {"action": "view", "coord": (2024, 12, 1, 46),
             "expect": {"item_available": True, "answer_hidden": True, "attempt_count": 0}},
            {"action": "submit", "coord": (2024, 12, 1, 46), "submitted": "A",
             "expect": {"stage": "attempt_wrong", "answer_keys": "B", "correct": False,
                        "attempt_count": 1, "tier": "plan_insufficient_data"}},
            {"action": "view", "coord": (2024, 12, 1, 51),
             "expect": {"item_available": True, "answer_hidden": True, "attempt_count": 1}},
            {"action": "submit", "coord": (2024, 12, 1, 51), "submitted": "D",
             "expect": {"stage": "attempt_correct", "answer_keys": "D", "correct": True,
                        "attempt_count": 2, "tier": "plan_insufficient_data"}},
            {"action": "submit", "coord": (2024, 12, 1, 46), "submitted": "E",
             "expect": {"stage": None, "answer_keys": None, "correct": None,
                        "attempt_count": 2, "tier": "plan_insufficient_data"}},
        ),
    },
)

# Writing/translation is evaluated offline through the cached task and durable
# ledger only. Model feedback is deliberately not requested in this scenario.
DRAFT_CASES = (
    {
        "id": 5,
        "name": "翻译原稿保存与跨会话恢复",
        "coord": (2024, 12, 1, "translation"),
        "draft_text": "The Hong Kong-Zhuhai-Macao Bridge connects three cities.",
    },
)

# ---------- 纯函数区(可单测,导入不花钱) ----------


def sections_present(raw: str | None) -> int:
    """八节标题命中了几个;空返回/截断就是小于 8。"""
    lines = [line.strip().strip("*").strip() for line in (raw or "").splitlines()]
    return sum(1 for name in _SECTIONS if any(l.startswith(name) for l in lines))


def score_step(expect: dict, actual: dict) -> list[str]:
    """返回**不符字段名**的列表,全中返回 [];不返回布尔是为了一眼看出败在哪项。

    ★ "字段缺失"和"值是 None"必须分开:期望 `None`、actual 里键都不存在,
      是"系统压根没写这个字段",也要判不符 —— 用 .get() 会把两者混成一个。
    """
    return sorted(
        key
        for key, want in expect.items()
        if key not in actual or actual[key] != want
    )


def run_practice_case(case: dict, out_dir: str) -> list[dict]:
    """Run one practice sequence through the deterministic Service path."""
    session_id = f"practice-scenario-{case['id']}"
    service = Service(ragconfig(), session_id=session_id,
                      learning_path=Path(out_dir) / f"learning-{case['id']}.jsonl")
    service.episode = Episode(session_id, out_dir=out_dir)
    rows = []
    for index, step in enumerate(case["steps"], 1):
        coord = step["coord"]
        if step["action"] == "view":
            item = service.practice_question(*coord)
            safe_keys = ({"question_number", "passage_text", "stem", "options"}
                         if 46 <= coord[3] <= 55 else
                         {"question_number", "stem", "paragraphs"}
                         if 36 <= coord[3] <= 45 else
                         {"question_number", "practice_text", "words"})
            actual = {
                "item_available": item is not None,
                "answer_hidden": item is None or set(item) == safe_keys,
                "attempt_count": service.practice_progress()["attempt_count"],
            }
        else:
            result = service.submit_practice_answer(*coord, step["submitted"])
            trace = service.episode.last() if result else None
            progress = service.practice_progress()
            actual = {
                "stage": trace.get("stage") if trace else None,
                "submitted": result.get("submitted") if result else None,
                "answer_keys": trace.get("answer_keys") if trace else None,
                "correct": result.get("correct") if result else None,
                "attempt_count": progress["attempt_count"],
                "tier": progress["tier"],
            }
        rows.append({
            "scenario_id": case["id"], "scenario_name": case["name"],
            "step": index, "action": step["action"], "expect": step["expect"],
            "actual": actual, "failed": score_step(step["expect"], actual),
        })
    return rows


def run_draft_case(case: dict, out_dir: str) -> list[dict]:
    """Verify a real cached draft task, save, and reopen without calling an LLM."""
    path = Path(out_dir) / f"draft-learning-{case['id']}.jsonl"
    service = Service(ragconfig(), session_id=f"draft-scenario-{case['id']}",
                      learning_path=path)
    coord = case["coord"]
    task = service.draft_question(*coord)
    view = {
        "item_available": task is not None,
        "sample_hidden": task is not None and set(task) == {"section", "task_text", "review_scope"},
    }
    saved = service.submit_draft(*coord, case["draft_text"])
    reopened = Service(ragconfig(), session_id=f"draft-reopen-{case['id']}",
                       learning_path=path)
    history = reopened.draft_history(coord[3])
    progress = reopened.learning_progress(preferred_section=coord[3])
    restored = {
        "latest_feedback_status": progress["latest_feedback_status"],
        "draft_restored": len(history) == 1 and history[0]["draft_text"] == case["draft_text"],
    }
    checks = (
        ("view", view, {"item_available": True, "sample_hidden": True}),
        ("submit", {"status": saved["status"]}, {"status": "saved"}),
        ("reopen", restored, {"latest_feedback_status": "pending", "draft_restored": True}),
    )
    return [
        {"scenario_id": case["id"], "scenario_name": case["name"], "step": index,
         "action": action, "expect": expect, "actual": actual,
         "failed": score_step(expect, actual)}
        for index, (action, actual, expect) in enumerate(checks, 1)
    ]


def _resolve(raw_expect: dict, coord: tuple | None) -> tuple[dict, str | None]:
    """把 KEYS 占位换成该步真实答案字母;返回 (填好的期望, 该步真实 KEYS 或 None)。"""
    # 每一步都要求"这一轮没报错" —— 它不是可选指标,所以在这里统一加进期望。
    raw_expect = {"error": None, **raw_expect}
    if coord is None:
        return dict(raw_expect), None
    year, month, exam_set, qnum = coord
    parsed = load_set(year, month, exam_set)
    if parsed and 26 <= qnum <= 35:
        pair = get_section_a_answer(parsed, qnum)
        keys = pair[0] if pair else None
    else:
        keys = get_answer(parsed, qnum) if parsed else None
    return {k: (keys if v == KEYS else v) for k, v in raw_expect.items()}, keys


def _observe_reply(expect: dict, coord: tuple | None, reply: str, keys: str | None):
    """回包里那个"答案字母"的观测值;期望里没写 reply_answer 的步骤返回 None。

    ★ 不搜单个字母:讲解正文里满篇都是别的段落字母。按 stage 分两种稳定格式查。
    """
    if "reply_answer" not in expect or keys is None:
        return None
    if expect.get("stage") == "answer":
        if 26 <= coord[3] <= 35:
            return keys if f"第{coord[3]}空选 {keys},填 " in reply else None
        # 整串稳定格式(service.py:371),后面可能跟 "(原文开头…)",所以用 in 不用 ==。
        return keys if f"第{coord[3]}题答案:{keys}" in reply else None
    # 讲解模式:复用 smoke_eval 的八节解析器,MATCH 时抠出的字母就是 keys。
    return classify(reply, keys)[1]


def _run_step(service: Service, case: dict, idx: int, question: str,
              coord: tuple | None, expect: dict, keys: str | None) -> dict:
    """跑一步,回一行结果(不写盘)。"""
    started = time.perf_counter()
    error = None
    try:
        reply = service.process(question)
    except Exception as exc:        # process 内部已兜底,这里只是最后一道保险
        reply, error = "", repr(exc)
        traceback.print_exc()
    latency_ms = int((time.perf_counter() - started) * 1000)

    trace = service.episode.last() or {}
    actual = {
        "intent": trace.get("intent"),
        "state_op": trace.get("state_op"),
        "stage": trace.get("stage"),
        "filters": trace.get("filters"),
        "answer_keys": trace.get("answer_keys"),
        "reply_answer": _observe_reply(expect, coord, reply, keys),
        "sections_8": (
            sections_present(reply) if expect.get("stage") == "explanation" else None
        ),
        "error": error or trace.get("error"),
    }
    failed = score_step(expect, actual)
    if trace.get("turn") != idx:
        # 轨迹写失败会读到上一轮的行 —— 那是静默误判为通过,必须显式标出来。
        failed = sorted({*failed, "trace"})
    return {
        "scenario_id": case["id"],
        "scenario_name": case["name"],
        "step": idx,
        "question": question,
        "expect": expect,
        "actual": actual,
        "failed": failed,
        "latency_ms": latency_ms,
        "reply": reply,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def _summarize(rows: list[dict]) -> None:
    """逐项拆开报,分母按"这一步适用不适用"算 —— 只报一个总分等于把信息丢了。"""
    metrics = ("intent", "state_op", "stage", "filters", "answer_keys",
               "reply_answer", "sections_8", "error")
    print("\n---- 汇总 ----")
    print(f"步骤完全通过       {sum(1 for r in rows if not r['failed'])}/{len(rows)}")
    for key in metrics:
        applicable = [r for r in rows if key in r["expect"]]
        if not applicable:
            continue
        ok = sum(1 for r in applicable if key not in r["failed"])
        print(f"  {key:16s} {ok}/{len(applicable)}")
    bad = [r for r in rows if r["failed"]]
    if bad:
        print("\n---- 未通过的步 ----")
        for r in bad:
            print(f"  [{r['scenario_id']}-{r['step']}] {r['question']} → {r['failed']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, default=0,
                        help="只跑指定 scenario_id(验链路用,只打印不写文件)")
    parser.add_argument("--practice", action="store_true", help="离线运行逐题练习场景,只打印")
    args = parser.parse_args()

    if args.practice:
        reading_cases = [case for case in PRACTICE_CASES if not args.only or case["id"] == args.only]
        draft_cases = [case for case in DRAFT_CASES if not args.only or case["id"] == args.only]
        if not reading_cases and not draft_cases:
            print(f"没有 practice scenario_id == {args.only} 的场景")
            return
        with tempfile.TemporaryDirectory(prefix="practice_scenario_") as out_dir:
            rows = [row for case in reading_cases for row in run_practice_case(case, out_dir)]
            rows += [row for case in draft_cases for row in run_draft_case(case, out_dir)]
        for row in rows:
            print(f"[{row['scenario_id']}-{row['step']}] {row['action']} failed={row['failed']}")
        print(f"练习场景通过 {sum(not row['failed'] for row in rows)}/{len(rows)} 步；未写评测结果文件。")
        return

    cases = [c for c in CASES if not args.only or c["id"] == args.only]
    if not cases:
        print(f"没有 scenario_id == {args.only} 的场景")
        return

    # ★ 轨迹一律写临时目录。Service 内部先用默认 out_dir 建了 Episode(不落盘),
    #   这里覆盖掉 —— 必须在第一次 process() 之前,否则会写进项目根的 episodes/。
    out_dir = tempfile.mkdtemp(prefix="scenario_eval_")
    rows = []
    for case in cases:
        sid = f"scenario-{case['id']}"
        service = Service(ragconfig(), session_id=sid)
        service.episode = Episode(sid, out_dir=out_dir)   # 每个场景独立会话
        for idx, (question, coord, raw_expect) in enumerate(case["steps"], 1):
            expect, keys = _resolve(raw_expect, coord)
            if coord is not None and keys is None:
                print(f"[{case['id']}-{idx}] 缓存里没有 {coord} 的 KEYS,跳过这步")
                continue
            row = _run_step(service, case, idx, question, coord, expect, keys)
            rows.append(row)
            print(f"[{case['id']}-{idx}] {str(row['actual']['stage']):18s} "
                  f"intent={str(row['actual']['intent']):12s} "
                  f"op={str(row['actual']['state_op']):5s} "
                  f"{row['latency_ms']}ms failed={row['failed']}")
            if "filters" in row["expect"]:
                print(f"      filters={row['actual']['filters']}")

    _summarize(rows)

    if args.only:
        print("\n--only 模式:只打印,不写文件。")
        return

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:   # "w":正式跑每次覆盖,不追加历史
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n明细写入 {OUT_PATH}({len(rows)} 行)")


if __name__ == "__main__":
    main()
