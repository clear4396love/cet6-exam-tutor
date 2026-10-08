# -*- coding: utf-8 -*-
"""Section B 段落匹配(36-45)解析器:PDF → 段落/题干 → JSON 缓存。"""
import json
import os
import re
import sys
from rich import print as r
from langchain_community.document_loaders import PyMuPDFLoader

from reading.paddle_ocr import table_answers

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
CACHE_DIR = os.path.join(BASE_DIR, "reading_sectionB")

PARA_RE = re.compile(r"^(?:\[([A-Z])\]|([A-Z])\))\s*(.*)$")  # [A] 或 A) 段落
STEM_RE = re.compile(r'^(\d{1,2})[. ](?!\d)\s*(.*)$')  # 36. 题干
ANSWER_RANGE_RE = re.compile(r"[【\[]([0-9]{1,2})-([0-9]{1,2})[】\]]\s*([A-Z]+)")


class paragraph_matching:
    # define() 切块的起止标题;子类想切别的 Section,覆盖这两个类属性即可
    start = "Section B"          # 起点
    end = "Section C"            # 终点;None 或 "" → 表示没结尾,切到底

    def pdf_load(self, pdf_path):
        return PyMuPDFLoader(pdf_path).load()

    def define(self, pages):
        """切 [Reading Comprehension, Translation) 里从 start 到 end 的块。
        end 为空(None 或 "")→ 表示没结尾,一直切到底。"""
        document = "\n".join(page.page_content for page in pages)
        read_idx = document.find("Reading Comprehension")
        end_mark = document.find("Translation", read_idx)
        reading_block = document[read_idx:end_mark]
        b = reading_block.find(self.start)
        if not self.end:                   # None 或 "" 都算"没有结尾" → 切到底
            return reading_block[b:]
        c = reading_block.find(self.end, b)
        return reading_block[b:c] if c != -1 else reading_block[b:] 

    def extract_reading(self, pages):
        """Section B 块 → (paragraphs{字母: 正文}, questions{题号: 题干})。"""
        section_b = self.define(pages)      # 关键修复:块自己切,不再用不存在的变量
        paragraphs = {}
        questions = {}
        current = None
        for line in section_b.splitlines():
            line = line.strip()
            if not line:
                continue

            line_paragraph = PARA_RE.match(line)      # 段落行 → 开新段
            if line_paragraph:
                letter = line_paragraph.group(1) or line_paragraph.group(2)
                current = ("p", letter)
                paragraphs[letter] = line_paragraph.group(3)
                continue

            line_question = STEM_RE.match(line)       # 题干行 → 开新题
            if line_question:
                current = ("q", int(line_question.group(1)))
                questions[current[1]] = line_question.group(2)
                continue

            # 既不是段落也不是题干 → 是上一段/上一题的续行,拼到后面
            if current is None:
                continue
            key, value = current
            if key == "p":
                paragraphs[value] += " " + line
            else:
                questions[value] += " " + line
        return paragraphs, questions

    def parse_keys(self, pages):
        """KEYS 块 '数字组+字母组' 按位置配对 → {题号: 答案字母}。"""
        text = "\n".join(p.page_content for p in pages)
        header_re = re.compile(r"^(KEYS|Part|Writing|Listening|Reading|Translation|Section)")
        answers = {}

        for match in ANSWER_RANGE_RE.finditer(text):
            first, last = int(match.group(1)), int(match.group(2))
            letters_in_range = match.group(3)
            numbers = range(first, last + 1)
            if len(letters_in_range) == last - first + 1:
                answers.update(zip(numbers, letters_in_range))

        answers.update(table_answers(text, 26, 45))

        start = text.find("KEYS")
        if start == -1:
            return answers

        pending = []    # 当前组的题号
        letters = []    # 当前组的答案字母

        def flush():
            if pending and letters:
                for num, letter in zip(pending, letters):
                    answers[num] = letter
            pending.clear()
            letters.clear()

        for line in text[start:].splitlines():
            line = line.strip()
            if not line:
                continue
            if header_re.match(line):
                flush()
                continue
            tokens = line.split()
            if all(t.isdigit() for t in tokens):      # 数字行 → 新一组题号
                if letters:
                    flush()
                pending.extend(int(t) for t in tokens)
            elif all(re.fullmatch(r"[A-Z]", t) for t in tokens):  # 字母行 → 答案
                letters.extend(t for t in tokens)
        flush()
        return answers

    def json_load(self, year, month, exam_set):
        """有缓存就读缓存;没有就解析 PDF,拼 JSON 并写缓存。"""
        cache_name = f"{year}_{month}_{exam_set}.json"
        cache_path = os.path.join(CACHE_DIR, cache_name)

        if os.path.exists(cache_path):                 # 有缓存
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        pdf_name = f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_name)
        if not os.path.exists(pdf_path):               # 试卷不存在
            print(f"[pdf]")
            return None

        pages = self.pdf_load(pdf_path)
        paragraphs, question_stems = self.extract_reading(pages)
        answers = self.parse_keys(pages)

        result = {
            "year": year,
            "month": month,
            "exam_set": exam_set,
            "paragraphs": paragraphs,
            "questions": {},
        }
        for qnum, stem in question_stems.items():
            result["questions"][str(qnum)] = {
                "stem": stem,
                "answer": answers.get(qnum),
            }

        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result


if __name__ == "__main__":
    p = paragraph_matching()
    data = p.json_load(2022, 9, 1)
    if data is None:
        sys.exit(1)
    r(data)
