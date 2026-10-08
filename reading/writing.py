# -*- coding: utf-8 -*-
"""写作题解析:从 "begins with the sentence "..." You can make ..." 里抽作文题目。

CET6 写作指令的固定骨架(2022 年后新题型):
    ... write an essay that begins with the sentence "题目句" You can make ...
题目句 = 中间引号里的那句,是作文必须以此开头的指定句子。

注意尾部措辞有变体:make statements / make comments / cite examples,别把尾句写死。
"""
import os
import re
import json
from rich import print as r
from reading.sectionB_load import paragraph_matching

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
PARSED_DIR = os.path.join(BASE_DIR, "parsed_papers")

# 匹配"题目句":引号内容可同行也可跨行;兼容直引号 " 与弯引号 “ ”
ANCHOR = "begins with the sentence"
STEM_QUOTED = re.compile(r'["“](.*?)["”]', re.DOTALL)


class part_Writing(paragraph_matching):
    def parse_writing(self, pages):
        """全卷文字里找作文指令,抽出引号里的指定句(标题)。找不到返回 None。"""
        doc = "\n".join(p.page_content for p in pages)
        m = STEM_QUOTED.search(doc)
        if not m:
            return None
        return re.sub(r"\s+", " ", m.group(1)).strip()   # 跨行标题压平成一行

    def save(self, year, month, exam_set):
        """抽 writing 标题,并回 parsed_papers/{year}_{month}_{exam_set}.json(别的键不动)。"""
        pdf = os.path.join(PDF_DIR, f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf")
        if not os.path.exists(pdf):
            r(f"找不到 PDF")
            return
        pages = self.pdf_load(pdf)
        title = self.parse_writing(pages)
        cache = os.path.join(PARSED_DIR, f"{year}_{month}_{exam_set}.json")   # 真文件路径
        if os.path.exists(cache):              # 有旧文件 → 只换 writing 键,别的原样保留
            with open(cache, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"year": year, "month": month, "exam_set": exam_set}
        data["writing"] = title
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        r(f"writing 已并回 parsed_papers")
