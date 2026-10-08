# -*- coding: utf-8 -*-
"""PaddleOCR-VL 云端 OCR:整卷 PDF → 每页 markdown → 伪 pages 喂 careful_reading。

把官方脚本的「提交 job → 轮询 → 下载 jsonl → 落 md」封装成可复用工具:
- 缓存:每卷 md 落 databases/ocr_pdfs/<试卷名>_paddle/(每页一个 doc_NNN.md + meta.json)
- 有缓存秒回,不重复调 API;没缓存才上传外网跑。
- pages(pdf) 返回清洗后的伪页面对象(带 .page_content),直接喂 careful_reading.parse
  (define/parse 只取 page_content,与 PyMuPDFLoader 页面对象等价,无需改解析逻辑)。

用法:
    from paddle_ocr import pages
    ps = pages(pdf_path)      # 每页 SimpleNamespace(page_content=清洗后的 md 文本)
"""
import json
import os
import re
import sys
import time
from types import SimpleNamespace

import requests
from dotenv import load_dotenv

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
OCR_DIR = os.path.join(BASE_DIR, "databases", "ocr_pdfs")

OPTIONAL_PAYLOAD = {
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useLayoutDetection": True,
    "useChartRecognition": False,
    "markdownIgnoreLabels": [
        "number",
        "footnote",
        "header",
        "header_image",
        "footer",
        "footer_image",
        "aside_text",
    ],
}


def auth_headers() -> dict:
    """在真正请求前才读取令牌，避免在源码和模块全局中保留密钥。"""
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    token = os.getenv("PADDLE_OCR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("缺少 PADDLE_OCR_TOKEN 环境变量")
    return {"Authorization": f"bearer {token}"}


def _cache_dir(pdf: str) -> str:
    """该 PDF 的 paddle md 缓存目录(<同名>_paddle/)。"""
    stem = os.path.basename(pdf)[:-4]
    return os.path.join(OCR_DIR, stem + "_paddle")


def has_cache(pdf: str) -> bool:
    """有没有完整可复用的 paddle md 缓存(有 meta.json 即视为有)。"""
    return os.path.exists(os.path.join(_cache_dir(pdf), "meta.json"))


def submit(pdf: str) -> str:
    """上传本地 PDF,返回 jobId。"""
    with open(pdf, "rb") as f:
        data = {"model": MODEL, "optionalPayload": json.dumps(OPTIONAL_PAYLOAD)}
        resp = requests.post(JOB_URL, headers=auth_headers(), data=data,
                             files={"file": f}, timeout=300)
    if resp.status_code != 200:
        raise RuntimeError(f"提交失败 HTTP {resp.status_code}: {resp.text}")
    job_id = resp.json()["data"]["jobId"]
    print(f"[paddle] 已提交 {os.path.basename(pdf)} job {job_id}")
    return job_id


def wait(job_id: str) -> str:
    """轮询到 done,返回 jsonl 下载地址;failed 抛错。"""
    while True:
        resp = requests.get(
            f"{JOB_URL}/{job_id}", headers=auth_headers(), timeout=60
        )
        if resp.status_code != 200:
            raise RuntimeError(f"查询失败 HTTP {resp.status_code}: {resp.text}")
        data = resp.json()["data"]
        state = data["state"]
        if state == "pending":
            print("  pending...")
        elif state == "running":
            prog = data.get("extractProgress") or {}
            if prog.get("totalPages"):
                print(f"  running {prog.get('extractedPages')}/{prog.get('totalPages')} 页...")
            else:
                print("  running...")
        elif state == "done":
            print("  done")
            return data["resultUrl"]["jsonUrl"]
        elif state == "failed":
            raise RuntimeError(f"OCR 失败: {data.get('errorMsg')}")
        time.sleep(5)


def download(jsonl_url: str):
    """拉 jsonl，按页保留 Markdown 和 Paddle 版面结构。"""
    resp = requests.get(jsonl_url, timeout=600)
    resp.raise_for_status()
    pages = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        result = json.loads(line).get("result") or {}
        for res in result.get("layoutParsingResults") or []:
            md = (res.get("markdown") or {}).get("text") or ""
            pages.append({
                "markdown": md,
                "layout": res.get("prunedResult") or {},
            })
    if not pages:
        raise RuntimeError("jsonl 里没有解析结果")
    return pages


def ensure_mds(pdf: str, force: bool = False):
    """有完整缓存 → 直接返回页数;没有 → 上传 API 跑并落缓存。"""
    d = _cache_dir(pdf)
    meta_path = os.path.join(d, "meta.json")
    if not force and os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        files = [f for f in os.listdir(d) if f.startswith("doc_") and f.endswith(".md")]
        if len(files) == meta.get("pages"):
            print(f"[paddle] 复用缓存 {os.path.relpath(d)} ({len(files)} 页)")
            return meta["pages"]

    pages = download(wait(submit(pdf)))
    os.makedirs(d, exist_ok=True)
    for i, page in enumerate(pages):
        with open(os.path.join(d, f"doc_{i:03d}.md"), "w", encoding="utf-8") as f:
            f.write(page["markdown"])
        with open(os.path.join(d, f"doc_{i:03d}.json"), "w", encoding="utf-8") as f:
            json.dump(page["layout"], f, ensure_ascii=False, indent=2)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"pages": len(pages), "model": MODEL}, f, ensure_ascii=False, indent=2)
    print(f"[paddle] 落缓存 {os.path.relpath(d)} ({len(pages)} 页)")
    return len(pages)


def clean(md: str) -> str:
    """把一页 md 还原成近似文字层的纯文本行。
    起步只去行首 markdown 记号;试点若见到表格竖线/加粗等再按需补规则。"""
    lines = []
    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = re.sub(r"^(#{1,6}\s*|[-*+]\s+|>\s+)", "", line).strip()
        line = re.sub(r"^5[Oo](?=[.)]\s)", "50", line)
        lines.append(line)
    return "\n".join(lines)


def pages(pdf: str) -> list:
    """扫描版 PDF → 清洗后每页一个 SimpleNamespace(page_content=...),喂 careful_reading。"""
    ensure_mds(pdf)
    d = _cache_dir(pdf)
    files = sorted(f for f in os.listdir(d) if f.startswith("doc_") and f.endswith(".md"))
    if not files:
        raise RuntimeError(f"paddle 缓存为空: {d}")
    objs = []
    for f in files:
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            objs.append(SimpleNamespace(page_content=clean(fh.read())))
    return objs


# ---- KEYS 答案页:Paddle 把它渲染成 HTML 表格(数字行 + 下一行字母)----
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)


def _table_rows(text: str) -> list:
    """把 md 里所有 <table> 行拉成 [cells],每个 cell 是去 HTML 后的纯文本。"""
    rows = []
    for tr in _TR.finditer(text):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in _CELL.findall(tr.group(1))]
        if cells:
            rows.append(cells)
    return rows


def table_answers(text: str, first: int, last: int) -> dict[int, str]:
    """从相邻的题号行和答案字母行提取指定题号范围。"""
    rows = _table_rows(text)
    got = {}
    for i in range(len(rows) - 1):
        nums, lets = rows[i], rows[i + 1]
        if len(nums) != len(lets) or not nums:
            continue
        if not all(re.fullmatch(r"\d+", number) for number in nums):
            continue
        if not all(re.fullmatch(r"[A-Z]", letter) for letter in lets):
            continue
        for number, letter in zip(nums, lets):
            question = int(number)
            if first <= question <= last:
                got[question] = letter
    return got


def keys_46_55(pages: list):
    """从 Paddle md 的 KEYS 表格捞 46-55 答案。
    规则:数字行 + 紧邻下一行全 A-D 字母行才认;46-55 读全 10 个 → {q: 字母};否则 None。"""
    text = "\n".join(p.page_content for p in pages)
    got = table_answers(text, 46, 55)
    if all(q in got for q in range(46, 56)):
        return {str(q): got[q] for q in range(46, 56)}
    return None


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else ""
    if not pdf or not os.path.exists(pdf):
        print("用法: python paddle_ocr.py <pdf路径>")
        sys.exit(1)
    ps = pages(pdf)
    print(f"共 {len(ps)} 页")
    for i, pg in enumerate(ps):
        print(f"--- 页 {i + 1} ({len(pg.page_content)} 字) ---")
        print(pg.page_content[:600])
