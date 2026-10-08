# -*- coding: utf-8 -*-
"""Phase 8:Section A 失败卷重扫 + 新旧缓存对照(6 套)。

- OCR 只走 submit → wait → download,原始 markdown 原样落到
  eval/ocr_spike/fresh_ocr/<卷>/(不调 ensure_mds / 不调 pages / 不碰 databases/ocr_pdfs)。
- 解析新侧:clean() 之后喂 Cloze_Passage().extract();旧侧:缓存完整性检查通过才调 pdf_load()。
- 不调 save(),不写 parsed_papers,**不向重复卷/无答案卷/冲突卷发任何请求**。

用法:
    python eval/batch_section_a.py --limit 1     # 冒烟一卷
    python eval/batch_section_a.py               # 跑完剩余卷(已完成的自动跳过)
    python eval/batch_section_a.py --force       # 强制重跑
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
from types import SimpleNamespace

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
sys.path.insert(0, os.path.join(BASE, "reading"))
sys.path.insert(0, BASE)

# token 在父级 .env(exam-tutor/.env 不存在),Phase 7 起就是这么加载的;不改产品代码。
# load_dotenv 默认不覆盖已有变量,paddle_ocr.auth_headers() 之后再读也不会被冲掉。
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.normpath(os.path.join(BASE, "..", ".env")))

from paddle_ocr import MODEL, clean, download, submit, wait  # noqa: E402
from sectionA_load import OPT_RE, PASSAGE_RE, Cloze_Passage  # noqa: E402

PDF_DIR = os.path.join(BASE, "databases", "试卷")
OLD_DIR = os.path.join(BASE, "databases", "ocr_pdfs")
FRESH_DIR = os.path.join(BASE, "eval", "ocr_spike", "fresh_ocr")
BLANK_RE = re.compile("underline.([0-9]{2})")

# 本轮范围:5 套旧侧失败的卷 + 1 套已成功的对照卷。写死,避免手滑扩大扫描面。
SETS = [
    ("CET6_2021年12月_第2套_真题", "2021_12_2"),
    ("CET6_2021年6月_第1套_真题", "2021_6_1"),
    ("CET6_2022年12月_第3套_真题", "2022_12_3"),
    ("CET6_2023年6月_第3套_真题", "2023_6_3"),
    ("CET6_2020年12月_第2套_真题", "2020_12_2"),
    ("CET6_2022年6月_第1套_真题", "2022_6_1"),  # 对照卷
]


# ---- 新侧:重新 OCR(只 submit/wait/download,原始 md 原样落盘)----

def fresh_done(stem: str) -> bool:
    """新结果目录里 md 个数 == 新 meta 的 pages(OCR 返回结果数,不是 PDF 页数)。"""
    d = os.path.join(FRESH_DIR, stem)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.exists(meta_path):
        return False
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    files = [n for n in os.listdir(d) if n.startswith("doc_") and n.endswith(".md")]
    return len(files) == meta.get("pages")


def run_ocr(stem: str, pdf: str):
    """PDF → 新目录的 doc_NNN.md(原始 markdown)+ meta.json。返回 OCR 返回结果数。"""
    pages = download(wait(submit(pdf)))
    d = os.path.join(FRESH_DIR, stem)
    os.makedirs(d, exist_ok=True)
    for i, page in enumerate(pages):
        with open(os.path.join(d, "doc_%03d.md" % i), "w", encoding="utf-8") as f:
            f.write(page["markdown"])          # 原始,不经 clean()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"pages": len(pages), "model": MODEL,
                   "source_pdf": os.path.basename(pdf)}, f, ensure_ascii=False, indent=2)
    return len(pages)


def fresh_raw(stem: str) -> str:
    d = os.path.join(FRESH_DIR, stem)
    files = sorted(n for n in os.listdir(d) if n.startswith("doc_") and n.endswith(".md"))
    return "\n".join(open(os.path.join(d, n), encoding="utf-8").read() for n in files)


def fresh_pages(stem: str) -> list:
    """原始 md → clean() → 伪页面对象(与 paddle_ocr.pages 同样的形状)。"""
    d = os.path.join(FRESH_DIR, stem)
    files = sorted(n for n in os.listdir(d) if n.startswith("doc_") and n.endswith(".md"))
    out = []
    for n in files:
        with open(os.path.join(d, n), encoding="utf-8") as fh:
            out.append(SimpleNamespace(page_content=clean(fh.read())))
    return out


# ---- 旧侧:缓存完整性检查通过才允许调 pdf_load ----
# pdf_load() 是缓存感知入口,缓存缺失/不完整时底层会顺手上传,所以这里必须先挡一道。

def old_ready(stem: str) -> bool:
    d = os.path.join(OLD_DIR, stem + "_paddle")
    meta_path = os.path.join(d, "meta.json")
    if not os.path.exists(meta_path):
        return False
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    files = [n for n in os.listdir(d) if n.startswith("doc_") and n.endswith(".md")]
    return len(files) == meta.get("pages")


def old_meta_pages(stem: str):
    with open(os.path.join(OLD_DIR, stem + "_paddle", "meta.json"), encoding="utf-8") as f:
        return json.load(f).get("pages")


def old_raw(stem: str) -> str:
    """旧缓存的原始 markdown(ensure_mds 落盘时同样没经 clean)。"""
    d = os.path.join(OLD_DIR, stem + "_paddle")
    files = sorted(n for n in os.listdir(d) if n.startswith("doc_") and n.endswith(".md"))
    return "\n".join(open(os.path.join(d, n), encoding="utf-8").read() for n in files)


# ---- 第 7 条门禁的独立提取(自己按 tr/td 拆行,不复用产品侧的 table_answers)----

TAG_RE = re.compile(r"<[^>]+>")
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RANGE_RE = re.compile("[【\\[]([0-9]{1,2})-([0-9]{1,2})[】\\]]([A-Z]+)")


def rows_of(text: str) -> list:
    """先按 <tr>/<td> 拆行,每格去标签——HTML 里 26 和 27 之间隔着 </td><td>,裸文本正则够不着。"""
    rows = []
    for tr in TR_RE.findall(text):
        cells = [TAG_RE.sub("", c).strip() for c in TD_RE.findall(tr)]
        if cells:
            rows.append(cells)
    return rows


def keys_from_table(text: str) -> dict:
    """整行都是数字的题号行 + 紧邻整行都是 A-O 字母的答案行,按位置配对。"""
    got = {}
    rows = rows_of(text)
    for nums, letters in zip(rows, rows[1:]):
        if not nums or len(nums) != len(letters):
            continue
        if not all(n.isdigit() for n in nums):
            continue
        if not all(re.fullmatch(r"[A-O]", c) for c in letters):
            continue
        for n, c in zip(nums, letters):
            if 26 <= int(n) <= 35:
                got[int(n)] = c
    return got


def keys_from_ranges(text: str) -> dict:
    """范围式答案(【26-30】GEMKF 这类)单独解析。"""
    got = {}
    for m in RANGE_RE.finditer(text):
        first, last, letters = int(m.group(1)), int(m.group(2)), m.group(3)
        if len(letters) != last - first + 1:
            continue
        for n, c in zip(range(first, last + 1), letters):
            if 26 <= n <= 35:
                got[n] = c
    return got


def keys_string(raw: str) -> str:
    got = keys_from_table(raw)
    got.update(keys_from_ranges(raw))
    return "".join(got.get(n, "?") for n in range(26, 36))


# ---- 门禁 / 诊断 ----

def gates(section_a, raw: str) -> list:
    nums = [str(n) for n in range(26, 36)]
    if not section_a:
        return [("extract 返回 None", False)]
    words, qs = section_a["words"], section_a["questions"]
    ans = "".join(qs.get(n, {}).get("answer") or "?" for n in nums)
    return [
        ("词库 15 个 A-O", set(words) == set("ABCDEFGHIJKLMNO")),
        ("题号恰好 26-35", sorted(qs, key=int) == nums
         and (section_a["q_from"], section_a["q_to"]) == (26, 35)),
        ("10 题答案齐全", all(qs.get(n, {}).get("answer") for n in nums)),
        ("答案字母在词库内", all(qs.get(n, {}).get("answer") in words for n in nums)),
        ("answer_word 一致",
         all(qs[n]["answer_word"] == words.get(qs[n]["answer"]) for n in qs)),
        ("text 无 <table", "<table" not in section_a["text"]),
        ("答案串与 OCR 答案页一致", ans == keys_string(raw)),
    ]


def diag(raw: str) -> dict:
    return {
        "has_directions": bool(PASSAGE_RE.search(raw)),
        "blank_numbers": sorted({int(n) for n in BLANK_RE.findall(raw)}),
        "bank_letters": sorted({h.group(1) for h in OPT_RE.finditer(raw)}),
    }


def answer_string(section_a) -> str:
    if not section_a:
        return "-"
    return "".join(section_a["questions"].get(str(n), {}).get("answer") or "?"
                   for n in range(26, 36))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compare(old_sa, new_sa, old_pages, new_pages, old_diag, new_diag,
            old_raw_text, new_raw_text) -> list:
    """四项对照:页数 / 正文 / 词库 / 答案串。

    两边都解析失败时没有 section_a 可比,就退到原始 markdown 比:
    这正是本轮要回答的"内容变了没有"。
    """
    diffs = []
    if old_pages != new_pages:
        diffs.append("页数(OCR 返回结果数): 旧 %s → 新 %s" % (old_pages, new_pages))
    ratio = difflib.SequenceMatcher(None, norm(old_raw_text), norm(new_raw_text)).ratio()
    if norm(old_raw_text) != norm(new_raw_text):
        diffs.append("原始 OCR 内容不同(相似度 %.4f,长度 %d→%d)"
                     % (ratio, len(norm(old_raw_text)), len(norm(new_raw_text))))
    for field, label in (("has_directions", "Directions 原句"),
                         ("blank_numbers", "空位编号"),
                         ("bank_letters", "词库字母")):
        if old_diag.get(field) != new_diag.get(field):
            diffs.append("%s: 旧 %s → 新 %s"
                         % (label, old_diag.get(field), new_diag.get(field)))
    if (old_sa is None) != (new_sa is None):
        diffs.append("解析结果有无: 旧 %s → 新 %s"
                     % ("有" if old_sa else "None", "有" if new_sa else "None"))
    if old_sa and new_sa:
        if old_sa["text"] != new_sa["text"]:
            diffs.append("正文不同(长度 %d→%d)"
                         % (len(old_sa["text"]), len(new_sa["text"])))
        if old_sa["words"] != new_sa["words"]:
            diffs.append("词库不同: 旧 %s → 新 %s"
                         % (sorted(old_sa["words"]), sorted(new_sa["words"])))
        if answer_string(old_sa) != answer_string(new_sa):
            diffs.append("答案串不同: 旧 %s → 新 %s"
                         % (answer_string(old_sa), answer_string(new_sa)))
    return diffs, ratio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="已完成的新结果也重跑")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 卷(冒烟用)")
    args = ap.parse_args()

    os.makedirs(FRESH_DIR, exist_ok=True)
    targets = SETS[:args.limit] if args.limit else SETS
    report = []

    for stem, key in targets:
        pdf = os.path.join(PDF_DIR, stem + ".pdf")
        row = {"key": key, "stem": stem, "state": "", "gates": [], "diffs": []}
        t0 = time.time()
        try:
            if not os.path.exists(pdf):
                row["state"] = "skipped_no_pdf"
                report.append(row)
                print("[skip] %s: 找不到 PDF" % stem)
                continue
            if fresh_done(stem) and not args.force:
                print("[reuse] %s: 新结果已在,跳过 OCR" % stem)
                with open(os.path.join(FRESH_DIR, stem, "meta.json"), encoding="utf-8") as f:
                    row["ocr_pages"] = json.load(f)["pages"]
            else:
                row["ocr_pages"] = run_ocr(stem, pdf)

            raw = fresh_raw(stem)
            new_sa = Cloze_Passage().extract(fresh_pages(stem))
            row["new_answer"] = answer_string(new_sa)
            row["diagnosis"] = diag(raw)
            gate_list = gates(new_sa, raw)
            row["gates"] = [{"name": n, "ok": bool(ok)} for n, ok in gate_list]
            failed = [n for n, ok in gate_list if not ok]
            row["state"] = "success" if not failed else "parse_failed"
            row["reason"] = "; ".join(failed)

            if old_ready(stem):
                old_sa = Cloze_Passage().extract(Cloze_Passage().pdf_load(pdf))
                row["old_answer"] = answer_string(old_sa)
                row["old_pages"] = old_meta_pages(stem)
                o_raw = old_raw(stem)
                row["old_diagnosis"] = diag(o_raw)
                row["diffs"], row["raw_ratio"] = compare(
                    old_sa, new_sa, row["old_pages"], row.get("ocr_pages"),
                    row["old_diagnosis"], row["diagnosis"], o_raw, raw)
            else:
                row["state"] = "skipped_no_cache"
                row["reason"] = "旧 _paddle 缓存不完整,旧侧不解析"

            out_dir = os.path.join(FRESH_DIR, stem)
            if new_sa:
                y, m, s = key.split("_")
                with open(os.path.join(out_dir, "section_a.json"), "w", encoding="utf-8") as f:
                    json.dump({"year": int(y), "month": int(m), "exam_set": int(s),
                               "section_a": new_sa}, f, ensure_ascii=False, indent=2)
        except Exception as exc:                       # 单卷失败不拖垮整轮
            row["state"] = "error"
            row["reason"] = "%s: %s" % (type(exc).__name__, exc)
        row["seconds"] = round(time.time() - t0, 1)
        report.append(row)
        print("[%s] %s 新答案=%s 旧答案=%s 差异=%d 用时=%.1fs %s"
              % (row["state"], key, row.get("new_answer"), row.get("old_answer"),
                 len(row["diffs"]), row["seconds"], row["reason"]))
        for d in row["diffs"]:
            print("    - " + d)

    path = os.path.join(FRESH_DIR, "_report.json")
    if os.path.exists(path):                      # 续跑:同卷以最新一轮为准,不叠加
        with open(path, encoding="utf-8") as f:
            merged = {r["key"]: r for r in json.load(f)}
        merged.update({r["key"]: r for r in report})
        report = sorted(merged.values(), key=lambda r: r["key"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n汇总写入 %s" % os.path.relpath(path, BASE))
    for state in ("success", "parse_failed", "skipped_no_cache", "skipped_no_pdf", "error"):
        keys = [r["key"] for r in report if r["state"] == state]
        if keys:
            print("  %s: %d 套 %s" % (state, len(keys), keys))


if __name__ == "__main__":
    main()
