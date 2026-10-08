# -*- coding: utf-8 -*-
"""翻译题解析:抽 "Part IV Translation" 后面的中文原文段落。

指令句式 2020-2025 通用:
    ...you are allowed 30 minutes to translate a passage from Chinese into
    English. You should write your answer on Answer Sheet 2.
    中文段落(题目要你翻的那段)

只处理【文字层 PDF】(直接 pdf_load 读每页)。扫描版 PDF 文字层是空的,
翻译数据已入库 parsed_papers/*.json 的 translation 键,这里不再管。
"""
import json
import os
import re

from rich import print as r

from sectionB_load import paragraph_matching

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
PARSED_DIR = os.path.join(BASE_DIR, "parsed_papers")

# 翻译锚句(全格式通用;别匹配普通 "translation" 单词)
ANCHOR = "you are allowed 30 minutes to translate a passage"
# 中文段起点 = 锚句尾 "...answer on Answer Sheet 2." 之后
ANS = "answer sheet 2"
# 中文段之后的后继(KEYS / 下一 Part / 下一套卷头)→ 截到它之前
STOP = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:KEYS|Part\s+[IVX1-5]\b|Listening\b|答案|参考答案|第\s*[一二三1-3]\s*套)",
    re.IGNORECASE | re.MULTILINE)
CJK = re.compile(r"[一-鿿]")
# 部分文字层 PDF 自带 OCR 水印行("第8页，共8页 微信公众号：AMYOU"),整行删掉
FOOT = re.compile(r"第\s*\d+\s*页\s*[,，]\s*共\s*\d+\s*页|公众号|AMYOU")


class part_translation(paragraph_matching):
    start = "Part IV Translation"

    def parse_translation(self, pages):
        """逐页找翻译题,返回中文原文段落;找不到返回 None。"""
        for text in pages:
            i = text.lower().find(ANCHOR)
            if i == -1:
                continue
            seg = text[i + len(ANCHOR):]           # 锚句之后
            k = seg.lower().find(ANS)              # 跳掉 "...Answer Sheet 2."
            if k != -1:
                seg = seg[k + len(ANS):]
            seg = re.sub(r"^[.．。\s]+", "", seg)   # 句号后换行残留
            m = STOP.search(seg)                   # 同页若混进下一节就截掉
            if m:
                seg = seg[:m.start()]
            seg = "\n".join(ln for ln in seg.splitlines() if not FOOT.search(ln))
            seg = re.sub(r"\s+", " ", seg).strip()
            if len(CJK.findall(seg)) >= 20:
                return seg
        return None

    def save(self, year, month, exam_set):
        """抽翻译中文段,并入 parsed_papers/{year}_{month}_{exam_set}.json(别的键不动)。"""
        pdf = os.path.join(PDF_DIR, f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf")
        if not os.path.exists(pdf):
            r(f"找不到 PDF")
            return
        pages = [p.page_content for p in self.pdf_load(pdf)]
        title = self.parse_translation(pages)
        if not title:
            r(f"找不到翻译中文段")
            return
        cache = os.path.join(PARSED_DIR, f"{year}_{month}_{exam_set}.json")
        if os.path.exists(cache):              # 有旧文件 → 只加 translation 键,别的原样保留
            with open(cache, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"year": year, "month": month, "exam_set": exam_set}
        data["translation"] = title
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        r(f"translation 已并回 parsed_papers")
