# -*- coding: utf-8 -*-
"""离线批量建 Section B 段落匹配缓存(扫描版自动 OCR)。

数据导入流程(**只在离线建缓存时执行;问答阶段绝不触发 OCR**):
    for pdf in databases/试卷/*.pdf:
        has_text_layer(pdf)  → pages 直接读
        否则                  → ensure_text_layer(试卷/原件) 产出 ocr_pdfs 副本 → 读它
        extract_reading + parse_keys → 写 parsed_papers/<y>_<m>_<s>.json

目录分工(三个目录分离,防检索时重复入库):
    databases/试卷/      原件(文字版 + 纯扫描版)
    databases/ocr_pdfs/  ocrmypdf 补层副本(只放这里,不与原件混放)
    parsed_papers/       最终 JSON 缓存(检索问答只读这里)

用法:
    python build_papers.py                  # 默认:扫全部未缓存卷
    python build_papers.py 2022 9 2         # 只做指定一套
    python build_papers.py 2023 6 3 --dry-run   # 只解析报告,不写/不改 JSON
"""
import io
import json
import os
import re
import sys

# 只在前台 stdout 还不是 utf-8 时才包一层(textlayer_build import 进来时不再二次包装)
if (getattr(sys.stdout, "encoding", "") or "").lower() != "utf-8" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
CACHE_DIR = os.path.join(BASE_DIR, "parsed_papers")

from retrieval.paper_parser import paper      # 只 import 不改文件(红线)
from textlayer_build import OCR_DIR, has_text_layer, ensure_text_layer

# CET6_2022年9月_第2-3套_真题.pdf → 记 2022_9_2(取第 2 套;合卷只认前一号)
NAME_RE = re.compile(r"CET6_(\d{4})年(\d{1,2})月_第(\d+)(?:-\d+)?套_真题\.pdf$")


def ocr_copy_path(base_pdf: str) -> str:
    """扫描版原件对应的 ocr_pdfs 副本路径(<同名>_ocr.pdf)。"""
    return os.path.join(OCR_DIR, os.path.basename(base_pdf).rsplit(".", 1)[0] + "_ocr.pdf")


def _find_base_pdf(year: int, month: int, exam_set: int) -> str | None:
    """按 (年,月,套) 反查原件文件名(合卷 第2-3套 按前一号匹配)。"""
    for f in os.listdir(PDF_DIR):
        if not f.endswith(".pdf") or "_ocr" in f or "副本" in f:
            continue
        m = NAME_RE.match(f)
        if m and int(m.group(1)) == year and int(m.group(2)) == month:
            if exam_set == int(m.group(3)):          # 第2-3套 → exam_set=2
                return f
    return None


def _parse(pdf_path: str):
    """读一个(原件或 OCR 副本)→ (paragraphs, stems, answers)。
    answers 是卷内 KEYS 页真实数据(解析失败为空 dict,不是编的)。"""
    p = paper()
    pages = p.pdf_load(pdf_path)
    paragraphs, stems = p.extract_reading(pages)
    keys = p.parse_keys(pages)
    return paragraphs, stems, keys


def _process(year: int, month: int, exam_set: int, dry_run: bool, base_pdf: str) -> None:
    """对单卷:有文字层直接解析;扫描版 ensure OCR 副本后解析;写/报告缓存。"""
    cache_path = os.path.join(CACHE_DIR, f"{year}_{month}_{exam_set}.json")
    cached = os.path.exists(cache_path)
    key = f"{year}-{month}-{exam_set}"

    if has_text_layer(base_pdf):
        kind, read_path = "文字版", base_pdf
    else:
        copy = ocr_copy_path(base_pdf)
        if os.path.exists(copy):
            kind, read_path = "扫描版(OCR副本)", copy
        elif dry_run:
            print(f"[{key}] 扫描版且无 OCR 副本;--dry-run 不触发 OCR,跳过")
            return
        else:
            kind = "扫描版"
            print(f"[{key}] 扫描版,首次 OCR(约 1-3 分钟)...")
            read_path = ensure_text_layer(base_pdf)

    paragraphs, stems, keys = _parse(read_path)

    if not paragraphs and not stems:
        print(f"[{key}] {kind}:解析为空(OCR/版式不认),不写缓存")
        return

    # 只取本卷解析出的题(36-45)答案;没有 KEYS 就留空,绝不编
    answers = {str(q): keys[q] for q in sorted(stems, key=int)
               if q in keys and 36 <= int(q) <= 45}

    print(f"[{key}] {kind}:段落 {len(paragraphs)} / 题干 {len(stems)} / 答案 {len(answers)}")

    if dry_run:
        return
    if cached:
        print(f"[{key}] 已有缓存,跳过不覆盖: {cache_path}")
        return

    result = {
        "year": year, "month": month, "exam_set": exam_set,
        "source": "ocr" if "扫描版" in kind else "pdf",
        "ocr_verified": False,
        "answer_source": "keys",
        "answers": answers,
        "paragraphs": paragraphs,
        "questions": {},
    }
    for qnum, stem in stems.items():
        result["questions"][str(qnum)] = {
            "stem": stem,
            "answer": keys.get(qnum),      # None = 该题无 KEYS/没认到
        }

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    print(f"[{key}] 已写 {cache_path}")


def main(argv: list[str]) -> None:
    dry_run = "--dry-run" in argv
    nums = [int(a) for a in argv if a.lstrip("-").isdigit()]
    # 注意:--dry-run 里 'dry' 不是数字,不会误入 nums

    if len(nums) >= 3:
        year, month, exam_set = nums[0], nums[1], nums[2]
        base_pdf = _find_base_pdf(year, month, exam_set)
        if base_pdf is None:
            print(f"[找不到试卷文件] CET6_{year}年{month}月_第{exam_set}套_真题.pdf")
            sys.exit(1)
        print(f"== 指定 {year}-{month}-{exam_set} | {base_pdf} | dry_run={dry_run} ==")
        _process(year, month, exam_set, dry_run,
                 os.path.join(PDF_DIR, base_pdf))
        return

    # 全量模式:扫全部未缓存卷
    print("== 全量扫描 databases/试卷(未缓存卷) ==")
    for f in sorted(os.listdir(PDF_DIR)):
        if not f.endswith(".pdf") or "_ocr" in f or "副本" in f:
            continue
        m = NAME_RE.match(f)
        if not m:
            print(f"文件名不识别,跳过: {f}")
            continue
        year, month, exam_set = int(m.group(1)), int(m.group(2)), int(m.group(3))
        cache_path = os.path.join(CACHE_DIR, f"{year}_{month}_{exam_set}.json")
        if os.path.exists(cache_path):
            continue                      # 已有缓存,懒建,不打日志
        _process(year, month, exam_set, dry_run, os.path.join(PDF_DIR, f))
    print("== 全量扫描结束 ==")


if __name__ == "__main__":
    main(sys.argv[1:])
