# -*- coding: utf-8 -*-
"""题目级结构化解析器：解析 Section B 段落匹配和 KEYS 答案。"""
import json
import os
import re
import sys

from langchain_community.document_loaders import PyMuPDFLoader
from rich import print as r


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
CACHE_DIR = os.path.join(BASE_DIR, "parsed_papers")

PARA_RE = re.compile(r"^([A-Z])\)\s*(.*)$")
STEM_RE = re.compile(r"^(\d{1,2})[. ](?!\d)\s*(.*)$")


class paper:
    """保留旧类名，避免 structured.py 等调用方跟着改。"""

    def pdf_load(self, pdf_path: str) -> list:
        """读取 PDF，返回逐页 Document。"""
        return PyMuPDFLoader(pdf_path).load()

    def extract_reading(self, pages) -> tuple[dict, dict]:
        """提取 Section B 的段落和 36~45 题干。"""
        paragraphs = {}
        questions = {}
        current = None

        document = "\n".join(page.page_content for page in pages)
        read_idx = document.find("Reading Comprehension")
        end_mark = document.find("Translation", read_idx)
        reading_block = document[read_idx:end_mark]

        section_b_start = reading_block.find("Section B")
        section_c_start = reading_block.find("Section C", section_b_start)
        section_b = reading_block[section_b_start:section_c_start]

        for raw_line in section_b.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            paragraph_match = PARA_RE.match(line)
            if paragraph_match:
                letter = paragraph_match.group(1)
                current = ("paragraph", letter)
                paragraphs[letter] = paragraph_match.group(2)
                continue

            question_match = STEM_RE.match(line)
            if question_match:
                question_number = int(question_match.group(1))
                current = ("question", question_number)
                questions[question_number] = question_match.group(2)
                continue

            if current is None:
                continue

            kind, key = current
            if kind == "paragraph":
                paragraphs[key] += " " + line
            else:
                questions[key] += " " + line

        return paragraphs, questions

    def parse_keys(self, pages) -> dict[int, str]:
        """把 KEYS 中的题号组和答案字母组按位置配对。"""
        text = "\n".join(page.page_content for page in pages)
        header_re = re.compile(
            r"^(KEYS|Part|Writing|Listening|Reading|Translation|Section)"
        )
        start = text.find("KEYS")
        answers = {}
        pending = []
        letters = []

        def flush():
            if pending and letters:
                for number, letter in zip(pending, letters):
                    answers[number] = letter
            pending.clear()
            letters.clear()

        for raw_line in text[start:].splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if header_re.match(line):
                flush()
                continue

            tokens = line.split()
            if all(token.isdigit() for token in tokens):
                if letters:
                    flush()
                pending.extend(int(token) for token in tokens)
            elif all(re.fullmatch(r"[A-Z]", token) for token in tokens):
                letters.extend(tokens)

        flush()
        return answers

    def json_load(self, year: int, month: int, exam_set: int):
        """优先读缓存；没有缓存时解析 PDF 并写入缓存。"""
        cache_name = f"{year}_{month}_{exam_set}.json"
        cache_path = os.path.join(CACHE_DIR, cache_name)

        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as file:
                return json.load(file)

        pdf_name = f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"[找不到试卷文件] {pdf_path}")
            return None

        pages = self.pdf_load(pdf_path)
        paragraphs, question_stems = self.extract_reading(pages)
        answers = self.parse_keys(pages)

        if not paragraphs and not question_stems:
            print(f"[解析为空] {pdf_path} 可能是扫描版,无法提取文字")
            return None

        result = {
            "year": year,
            "month": month,
            "exam_set": exam_set,
            "paragraphs": paragraphs,
            "questions": {},
        }
        for question_number, stem in question_stems.items():
            result["questions"][str(question_number)] = {
                "stem": stem,
                "answer": answers.get(question_number),
            }

        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        return result

    def json_load_cached(self, year: int, month: int, exam_set: int):
        """只读缓存;没有就直接 None —— 不解析 PDF、不写盘。

        缓存路径的拼法只留在这一个文件里,别在调用方复制第二份。
        """
        cache_path = os.path.join(CACHE_DIR, f"{year}_{month}_{exam_set}.json")
        if not os.path.exists(cache_path):
            return None
        with open(cache_path, "r", encoding="utf-8") as file:
            return json.load(file)


if __name__ == "__main__":
    parser = paper()
    data = parser.json_load(2022, 9, 1)
    if data is None:
        sys.exit(1)
    r(data)
