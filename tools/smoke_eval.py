"""讲解生成冒烟评测(10 题):真调模型,看答案节标题能不能稳定解析。

只走讲解生成分支(build_evidence → generate_structured → 解析),
不经过意图识别、状态机、降级出口 —— 结果不能叫"端到端"或"准确率"。

★ 本模块**导入时不碰模型**:所有真实调用和写盘都在 main() 里,
  这样 tests/test_smoke_eval_parser.py 可以安全地 import classify。

用法:
    python tools/smoke_eval.py            # 正式跑 10 题,覆盖写 eval/smoke_results.jsonl
    python tools/smoke_eval.py --only 1   # 只跑第 1 题验网络,只打印、不写文件
"""
import argparse
import json
import os
import re
import sys
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ragconfig  # noqa: E402
from retrieval.generation import AnswerGeneration  # noqa: E402
from retrieval.structured import (  # noqa: E402
    build_evidence,
    extract_mention_letter,
    get_answer,
    load_set,
)

OUT_PATH = os.path.join(PROJECT_ROOT, "eval", "smoke_results.jsonl")

# 每题最多调 2 次 —— 照抄线上"空返回重试一次"的兜底(service.py:321-323)。
MAX_ATTEMPTS = 2
MAX_TOKENS = 3000

# ★ 固定题表(不随机)。前 5 道顺问**不写答案字母** —— 写了等于把答案喂给模型。
#   后 5 道是"为什么不选X",X 都在同套缓存里真实存在,且 != 答案(第 9 条除外,那是对照例)。
CASES = (
    # (case_id, 用户原话)
    (1, "2024年12月第1套第43题为什么这样选"),
    (2, "2024年12月第1套第45题为什么这样选"),
    (3, "2024年6月第1套第38题为什么这样选"),
    (4, "2024年12月第2套第36题为什么这样选"),
    (5, "2024年12月第3套第38题为什么这样选"),
    (6, "2024年12月第1套第43题为什么不选A"),
    (7, "2024年12月第1套第41题为什么不选A"),
    (8, "2024年12月第1套第45题为什么不选B"),
    (9, "2024年12月第3套第44题为什么不选A"),
    (10, "2024年6月第1套第38题为什么不选A"),
)

# 从题面里抠出年月套和题号 —— 复用 locator 的正则思路,但这里只需要这 4 个数,
# 评测脚本不复用 parse_conditions 是因为它还会抽 section,而这里要的就是明确的 4 元组。
_COORD = re.compile(r"(20\d{2})年(\d{1,2})月第(\d)套第(\d{1,3})题")

# ---------- 纯函数区(可单测,导入不花钱) ----------

# 只认"整行标题":加粗(剥掉 ** 后)或独占一行的普通标题,两种共用一个正则。
_TITLE = re.compile(r"^为什么选\s*\[?([A-R])\]?\s*[。:：,，、]?$", re.I)
# 占位符没替换的两种真实写法 —— 必须先判,否则会落进 UNPARSEABLE,分类就错了。
_LITERAL = re.compile(r"^为什么选\s*\[(?:答案|原文)\]\s*[。:：,，、]?$", re.I)


def _strip_bold(line: str) -> str:
    """只剥成对的首尾 ** —— 这正是 markdown 加粗标题的形状。"""
    line = line.strip()
    if line.startswith("**") and line.endswith("**"):
        line = line[2:-2].strip()
    return line


def classify(raw: str, keys: str) -> tuple[str, str | None]:
    """逐行找答案节标题,返回 (类别, 抠出的字母)。

    ★ 必须逐行 + 行锚:讲解正文里本来就会反复出现"为什么选I""为什么不选A"这类字眼,
      在整篇里 search 抠到的往往是正文,不是标题。

    类别:MATCH / MISMATCH / PLACEHOLDER / UNPARSEABLE。
    """
    for line in (raw or "").splitlines():
        line = _strip_bold(line)
        if _LITERAL.match(line):
            return ("PLACEHOLDER", None)        # 占位符没替换,先拦
        found = _TITLE.match(line)
        if found:
            letter = found.group(1).upper()     # 模型可能写小写 i
            return ("MATCH" if letter == keys else "MISMATCH", letter)
    return ("UNPARSEABLE", None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, default=0,
                        help="只跑指定 case_id(验网络用,只打印不写文件)")
    args = parser.parse_args()

    cases = [c for c in CASES if not args.only or c[0] == args.only]
    if not cases:
        print(f"没有 case_id == {args.only} 的题")
        return

    generator = AnswerGeneration(ragconfig(), max_tokens=MAX_TOKENS)
    rows = []
    for case_id, question in cases:
        coord = _COORD.search(question)
        if coord is None:
            print(f"[{case_id}] 题面抠不出年月套题号:{question}")
            continue
        year, month, exam_set, qnum = coord.groups()
        year, month, exam_set, qnum = int(year), int(month), int(exam_set), int(qnum)

        parsed = load_set(year, month, exam_set)
        keys = get_answer(parsed, qnum) if parsed else None
        if not keys:
            print(f"[{case_id}] 缓存里没有 {year}年{month}月第{exam_set}套第{qnum}题的 KEYS")
            continue

        mention = extract_mention_letter(question)
        evidence = build_evidence(parsed, qnum, mention)

        raw, empty_count, error = "", 0, None
        started = time.perf_counter()            # 和 episode.py 同口径:毫秒级整轮耗时
        try:
            for _ in range(MAX_ATTEMPTS):
                raw = generator.generate_structured(question, evidence)
                if raw and raw.strip():
                    break
                empty_count += 1
        except Exception as exc:                 # 偶发网络/接口错误不能带塌整批
            error = repr(exc)
            print(f"[{case_id}] 调用失败:{error}")
            traceback.print_exc()
        latency_ms = int((time.perf_counter() - started) * 1000)

        category, answer_model = classify(raw, keys)
        row = {
            "case_id": case_id,
            "question": question,
            "answer_keys": keys,
            "answer_model": answer_model,
            "category": category,
            "empty_count": empty_count,
            "latency_ms": latency_ms,
            "raw_output": raw,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        if error:
            row["error"] = error
        rows.append(row)
        print(f"[{case_id}] {category:12s} 模型={answer_model or '-':2s} KEYS={keys} "
              f"空返回={empty_count} 耗时={latency_ms}ms")

    if args.only:
        print("\n--only 模式:只打印,不写文件。")
        return

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:   # "w":正式跑每次覆盖,不追加历史
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    print("\n---- 汇总 ----")
    print("  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"明细写入 {OUT_PATH}({len(rows)} 行)")


if __name__ == "__main__":
    main()
