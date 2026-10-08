# -*- coding: utf-8 -*-
"""Section C 仔细阅读(46-55)解析器:PDF → 两篇 passage(正文 + 每题题干/选项)→ JSON。

思路照 sectionB_load.py:define() 切出 Section C 区域 → 正则找题干和选项 →
KEYS 答案用父类的 parse_keys → 拼 JSON,并回 parsed_papers/<年>_<月>_<套>.json 的
顶层 section_c 键(原 Section B 的 flat 字段保留不动)。

不做 OCR / 文字层判断:pdf_load 直接吃父类(PyMuPDFLoader),PDF 能 get_text 出
文字就能解析;扫描版没文字层 → 切不出两篇 → 只提示,不覆盖已有 json。

用法:
    python sectionC_load.py 2025 6 1     # 解析指定卷
    python sectionC_load.py              # 没带参 → 跑默认演示卷 2025 6 1
"""
import json
import os
import re
import sys

from rich import print as r

from paddle_ocr import table_answers
from sectionB_load import paragraph_matching

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
PARSED_DIR = os.path.join(BASE_DIR, "parsed_papers")

# 分界行:Questions 46 to 50 / 51 to 55 ... are based on the following passage.
# re.I=忽略大小写;\\.?=结尾句号可有可无。用它把 Section C 切成两篇。
PASSAGE_RE = re.compile(
    r"Questions (4[6-9]|5[0-5]) to (5[0-5]) are based on the following passage\.?",
    re.I)

# 题干行:行首(可带空格)是 46.~55.。re.M=多行模式,让 ^ 认每一行开头;
# 只匹配 "46." 数字+点,真正的问题文字要靠 m.end() 往后另切。
STEM_RE = re.compile(r"^\s*(4[6-9]|5[0-5])\.", re.M)

# 选项:大写 A~D + 右括号,前面不能是字母/数字(免得正文里 1A) 混进来)。
# 每题 4 个,支持"一行两个选项"、"网格乱序 A,C,B,D"的真实排版。
OPT_RE = re.compile(r"(?<![A-Za-z0-9])([A-D])[.)]")


class careful_reading(paragraph_matching):
    # 父类 define() 在 [Reading Comprehension, Translation) 里切"从 start 起到底"的块
    start = "Section C"
    end = ""

    def parse_keys(self, pages):
        """沿用 Section B 答案解析，并补读 46–55 的 HTML 答案表。"""
        answers = super().parse_keys(pages)
        text = "\n".join(page.page_content for page in pages)
        answers.update(table_answers(text, 46, 55))
        return answers

    def split_passages(self, block: str) -> list[str]:
        """Section C 整块 → 两篇的原文。
        以两行 'Questions 46 to 50 / 51 to 55 ...' 分界;分界行按整行切
        """
        marks = []
        for m in PASSAGE_RE.finditer(block):
            marks.append(block.rfind("\n", 0, m.start()) + 1)   # rfind 的作用是"找到句子所在行的行首",+1 是跨过换行符对应换行符后的句子                  
        if len(marks) < 2:
            return []                        # 分界行没找全(扫描版没文字层)→ 返回空,不写文件
        return [block[marks[0]:marks[1]], block[marks[1]:]]

    _TAIL_RE = re.compile(
        r"^(Passage\s+One|Passage\s+Two|Part\s+[IVX]+|Section\s+[A-Z]|Reading Comprehension)\s*$")
    #定位各种标题行
    def trim_tail(self, chunk: str) -> str:
        """去掉 chunk 末尾残留的栏目标题行(如块尾 'Part IV'),避免混进最后一题的选项。"""
        lines = chunk.splitlines(keepends=True)
        while lines:
            t = lines[-1].strip()
            if not t or self._TAIL_RE.match(t):
                lines.pop()
            else:
                break
        return "".join(lines)

    def parse_passage(self, chunk: str, keys):
        """一篇 passage 的原文 → 每个题号一份 {stem, options, answer}。
        chunk 是这篇从分界行到篇尾的整段文字。"""
        chunk = self.trim_tail(chunk)
        stems = list(STEM_RE.finditer(chunk))
        if not stems:
            return None

        # 正文 = 篇首到第一题题干之前;滤掉分界行/空行/页码
        body = []
        for line in chunk[:stems[0].start()].splitlines():
            t = line.strip()
            if not t or t.isdigit():
                continue
            if re.match(r"^(Passage|Questions?|Directions?)\b", t):
                continue
            body.append(t)

        questions = {}
        for i, m in enumerate(stems):
            qnum = int(m.group(1))#获得题号
            seg_end = stems[i + 1].start() if i + 1 < len(stems) else len(chunk)

            # 从本题题号后面起,到下一题题号前,扫全部选项字母前缀
            hits = list(OPT_RE.finditer(chunk, m.end(), seg_end))
            # 题干 = 题号后面到第一个选项字母前(可能跨行)
            stem = chunk[m.end():hits[0].start()] if hits else chunk[m.end():seg_end]
            stem = re.sub(r"\s+", " ", stem).strip()

            # 选项:按字母前缀切每项文本。不管是"一行一个选项"、"一行挤两个"、
            # 还是"两列网格导致顺序变 A,C,B,D",都按字母前缀认,最后按 A→D 归位
            options = {}
            for k, hit in enumerate(hits):
                a = hit.end()                              # 选项文本从 ')' 后面开始
                b = hits[k + 1].start() if k + 1 < len(hits) else seg_end
                options[hit.group(1)] = re.sub(r"\s+", " ", chunk[a:b]).strip()
            options = {L: options[L] for L in "ABCD" if L in options}

            questions[str(qnum)] = {
                "stem": stem,
                "options": options,
                "answer": keys.get(qnum),        # KEYS 里没读到 → None
            }

        return {
            "q_from": int(stems[0].group(1)),
            "q_to": int(stems[-1].group(1)),
            "text": " ".join(body),
            "questions": questions,
        }

    def extract(self, pages)-> list:
        """PDF 页 → 两篇 passage ;切不出两篇就返回空列表,让 save 决定动不动 json。"""
        block = self.define(pages)
        keys = self.parse_keys(pages)
        passages = []
        for i, chunk in enumerate(self.split_passages(block), 1):
            pg = self.parse_passage(chunk, keys)
            if pg:
                pg["id"] = i
                passages.append(pg)
        return passages

    def save(self, year, month, exam_set):
        """解析该卷 Section C;切出两篇才把 section_c 并进 parsed_papers json。"""
        key = f"{year}_{month}_{exam_set}"
        pdf = os.path.join(PDF_DIR, f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf")
        if not os.path.exists(pdf):
            r(f"[跳] {year}-{month}-{exam_set} 找不到 PDF")
            return

        pages = self.pdf_load(pdf)
        passages = self.extract(pages)

        # ★ 没凑齐两篇就一个字都不写。writing 出去会把已有的好缓存清成空壳
        #   (扫描卷没有文字层时走的正是这条路),而上面的文档串说好了"切出两篇才并进"。
        if len(passages) < 2:
            r(f"[跳] {key} 只切出 {len(passages)} 篇 Section C,没凑齐两篇 → 不动已有缓存")
            return

        # 并回 parsed_papers:有旧文件就只换 section_c 键,Section B flat 字段原样留着
        cache = os.path.join(PARSED_DIR, f"{key}.json")
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"year": year, "month": month, "exam_set": exam_set}
        data["section_c"] = {"passages": passages}
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total = sum(len(pg["questions"]) for pg in passages)
        filled = sum(1 for pg in passages for q in pg["questions"].values() if q["answer"])
        r(f"[写] {key} 已并回 {len(passages)} 篇 / {total} 题 / {filled} 题带答案")


if __name__ == "__main__":
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    if len(nums) >= 3:
        y, m, s = int(nums[0]), int(nums[1]), int(nums[2])
    else:
        r("用法: python sectionC_load.py <年> <月> <套>,例: python sectionC_load.py 2025 6 1")
        y, m, s = 2024, 12, 1          # 没带参 → 跑默认演示卷
    careful_reading().save(y, m, s)
