import json
import os
import re
import sys

from rich import print as r

from paddle_ocr import pages as paddle_pages
from sectionB_load import paragraph_matching
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
PDF_DIR = os.path.join(BASE_DIR, "databases", "试卷")
PARSED_DIR = os.path.join(BASE_DIR, "parsed_papers")

# 词库选项:Paddle 可能输出 A) word 或 HTML 单元格里的 A. word。
OPT_RE = re.compile(r"(?<![A-Za-z0-9])([A-O])\s*[.)]\s*([A-Za-z][A-Za-z'-]*)")
# 词库字母顺序:15 个词,答案/词库都按 A→O 归位
WORDS = "ABCDEFGHIJKLMNO"
# 空位兼容旧文字层的 _26_ 和 Paddle Markdown 的 $ \underline{26} $。
STEM_RE = re.compile(r"(?:\$\s*)?(?:_+|\\underline\{)(\d{2})(?:_+|\})(?:\s*\$)?")
NUMBERED_BLANK_RE = re.compile(r"(?<!\d)(2[6-9]|3[0-5])(?!\d)")
QUESTION_RANGE_RE = re.compile(
    r"Questions?\s+26\s+to\s+35\s+are based on the following passage\.?", re.I
)
PASSAGE_RE=re.compile(r"You may not use any of the words in the bank more than once.")

class Cloze_Passage(paragraph_matching):
    start="Section A"
    end="Section B"

    def pdf_load(self, pdf_path):
        """Section A 统一使用 Paddle Markdown 缓存；缺缓存时由其负责 OCR。"""
        return paddle_pages(pdf_path)

    def _blanks_ready(self, text: str) -> bool:
        """26~35 十个空位是否凑齐(兜底只认空位结构,不认标题文字)。"""
        got = {int(m.group(1)) for m in STEM_RE.finditer(text)}
        return got >= set(range(26, 36))

    def define(self, pages):
        """父类只认 Reading Comprehension 字面当锚点，Paddle 有时没把那个标题转成
        文字(2021_12_2 该字面只在卷尾答案页出现，正文那页只输出 Part III / (40 minutes))，
        read_idx 于是落到卷尾、块退化成 1 个字符。块里凑不齐 26~35 空位时按空位兜底:
        26 之前最近的 Section A 起、35 之后最近的 Section B 止。"""
        block = super().define(pages)
        if self._blanks_ready(block):
            return block                     # 老路径正常 → 输出一行不变
        text = "\n".join(p.page_content for p in pages)
        if "Reading Comprehension" not in text:
            return block                     # 整卷没认出阅读横幅 → 不猜(2021_6_1 形状)
        hits = list(STEM_RE.finditer(text))
        first = next((m.start() for m in hits if int(m.group(1)) == 26), -1)
        last = next((m.start() for m in hits if int(m.group(1)) == 35), -1)
        if first == -1 or last == -1:
            return block
        heads = [m.start() for m in re.finditer(self.start, text) if m.start() < first]
        if not heads:
            return block
        end = text.find(self.end, last)
        if end == -1:                        # 没有 Section B 就退 Section C,再退文末
            end = text.find("Section C", last)
        cand = text[heads[-1] : end if end != -1 else len(text)]
        return cand if self._blanks_ready(cand) else block

    def split_passages(self, block: str) -> list[str]:
        """去除sectiona中的Directions(介绍部分)"""
        mark=[]
        for m in PASSAGE_RE.finditer(block):
            mark.append(block[m.end():])
        if mark:
            return mark
        # 整卷没有 Directions 原句(2022_12_3/2023_6_3 的 OCR 命中 0 次)
        # → 整块就是正文+词库,只掐掉行首的 Section A 标题
        if block.startswith(self.start):
            return [block[len(self.start):].lstrip()]
        return [block]

    def parse_passage(self, chunk: str, keys):
        choice = list(OPT_RE.finditer(chunk))      # 词库 A~O
        if not choice:
            return None
        # 正文 = 起点到词库第一个 A) 之前;HTML 词库要先退到 <table> 之前,
        # 否则表头 (<table…><tr><td…>) 会黏在正文尾部。用 rfind 取离词库最近的那个。
        # 删下划线时顺带吃掉前面的空格 (\s*),否则 "were ___26___." 删完会剩 "were ." 这种空格+句号
        stop = choice[0].start()
        html = chunk.rfind("<table", 0, stop)
        if html != -1:
            stop = html
        passage = QUESTION_RANGE_RE.sub("", chunk[:stop])
        blanks = list(STEM_RE.finditer(passage))
        numbered_blanks = False
        if not blanks:
            # 智谱会把空位只识别成裸数字。按 26→35 顺序找一组空位编号，
            # 略过正文中同样落在 26~35 的普通数字（如年龄）；只删除选中的编号。
            candidates = list(NUMBERED_BLANK_RE.finditer(passage))
            expected = 26
            for match in candidates:
                if int(match.group(1)) == expected:
                    blanks.append(match)
                    expected += 1
                    if expected == 36:
                        break
            if expected == 36:
                numbered_blanks = True
            else:
                blanks = []
        if not blanks:
            return None
        practice_text = None
        if [int(match.group(1)) for match in blanks] == list(range(26, 36)):
            practice_text = passage
            for match in reversed(blanks):
                number = match.group(1)
                practice_text = practice_text[:match.start()] + f"{{{{{number}}}}}" + practice_text[match.end():]
            practice_text = re.sub(r"\s+", " ", practice_text).strip()
        if numbered_blanks:
            body = passage
            for match in reversed(blanks):
                body = body[:match.start()] + body[match.end():]
        else:
            body = STEM_RE.sub("", passage)
        body = re.sub(r"\s+", " ", body).strip()

        # 词库:A) 到下一个字母) 之间的文本就是这个单词(照 sectionC 切选项
        # 的办法)。词库排版是两列网格、扫描顺序乱(如 A,I,B,J...),
        # 先按字母存,最后按 A→O 归位。一个词是字母/连字符/撇号组成的
        # (多词短语如 "give up" 也允许,只是空格不规整的先压成单个空格)
        raw = {hit.group(1): hit.group(2) for hit in choice}
        words = {L: raw[L] for L in WORDS if L in raw}
        if len(words) != 15:
            r(f"[词库缺] 只认到 {len(words)}/15 个词: {sorted(raw)}")

        questions = {}
        for m in blanks:
            qnum = int(m.group(1))
            letter = keys.get(qnum)            
            questions[str(qnum)] = {
                "answer": letter,
                "answer_word": words.get(letter),   # 该题答案字母对应的单词
            }
        result = {
            "q_from": int(blanks[0].group(1)),
            "q_to": int(blanks[-1].group(1)),
            "text": body,
            "words": words,
            "questions": questions,
        }
        if practice_text is not None:
            result["practice_text"] = practice_text
        return result


    def extract(self, pages):
        """PDF → 去掉 Directions → 解析成一篇的 dict(能跑的最小版)。"""
        block = self.define(pages)           # 父类:在 Reading Comprehension 里切 Section A → Section B
        keys = self.parse_keys(pages)        # 父类:整卷 KEYS → {26: "F", ...}(整型键)
        for chunk in self.split_passages(block):    # 去掉 Directions 后,正文+词库
            pg = self.parse_passage(chunk, keys)
            if pg and all(pg["questions"].get(str(n), {}).get("answer") for n in range(26, 36)):
                return pg
        return None

    def save(self, year, month, exam_set):
        """解析该卷 Section A,并回 parsed_papers json 顶层 section_a(别的键不动)。"""
        key = f"{year}_{month}_{exam_set}"
        pdf = os.path.join(PDF_DIR, f"CET6_{year}年{month}月_第{exam_set}套_真题.pdf")
        if not os.path.exists(pdf):
            r(f"找不到 PDF")
            return

        pages = self.pdf_load(pdf)
        pg = self.extract(pages)
        if not pg:                       # 没切出(扫描版/排版异常)→ 不写,别覆盖旧文件
            r(f"没解析出 Section A,不写文件")
            return

        cache = os.path.join(PARSED_DIR, f"{key}.json")
        if os.path.exists(cache):        # 有旧文件 → 只换 section_a 键,别的原样保留
            with open(cache, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"year": year, "month": month, "exam_set": exam_set}
        data["section_a"] = pg
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        filled = sum(1 for q in pg["questions"].values() if q["answer"])
        r(f"Section A 已并回 parsed_papers")


if __name__ == "__main__":
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    if len(nums) >= 3:
        y, m, s = int(nums[0]), int(nums[1]), int(nums[2])
    else:
        r("用法: python sectionA_load.py <年> <月> <套>,例: python sectionA_load.py 2025 6 1")
        y, m, s = 2024, 12, 1          # 没带参 → 跑默认演示卷
    Cloze_Passage().save(y, m, s)
