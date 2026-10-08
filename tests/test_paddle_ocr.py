import json
from types import SimpleNamespace

import pytest

from reading import paddle_ocr


def test_clean_repairs_question_50_without_touching_body_text():
    text = "5O. What does the passage suggest?\nThe report calls it 2O25 data."

    assert paddle_ocr.clean(text) == (
        "50. What does the passage suggest?\n"
        "The report calls it 2O25 data."
    )


def test_auth_headers_reads_project_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "PADDLE_OCR_TOKEN=dotenv-token\n", encoding="utf-8"
    )
    monkeypatch.delenv("PADDLE_OCR_TOKEN", raising=False)
    monkeypatch.setattr(paddle_ocr, "BASE_DIR", str(tmp_path))

    assert paddle_ocr.auth_headers() == {
        "Authorization": "bearer dotenv-token"
    }


def test_submit_uses_env_token_and_filters_page_margins(monkeypatch, tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {"data": {"jobId": "job-1"}},
        )

    monkeypatch.setenv("PADDLE_OCR_TOKEN", "test-token")
    monkeypatch.setattr(paddle_ocr.requests, "post", fake_post)

    assert paddle_ocr.submit(str(pdf)) == "job-1"
    assert captured["headers"] == {"Authorization": "bearer test-token"}
    payload = json.loads(captured["data"]["optionalPayload"])
    assert payload["useLayoutDetection"] is True
    assert payload["markdownIgnoreLabels"] == [
        "number",
        "footnote",
        "header",
        "header_image",
        "footer",
        "footer_image",
        "aside_text",
    ]


def test_submit_rejects_missing_token_before_upload(monkeypatch, tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.delenv("PADDLE_OCR_TOKEN", raising=False)
    monkeypatch.setattr(paddle_ocr, "BASE_DIR", str(tmp_path))

    def forbidden_post(*args, **kwargs):
        pytest.fail("缺少令牌时不应上传PDF")

    monkeypatch.setattr(paddle_ocr.requests, "post", forbidden_post)

    with pytest.raises(RuntimeError, match="PADDLE_OCR_TOKEN"):
        paddle_ocr.submit(str(pdf))


def test_download_keeps_markdown_and_layout(monkeypatch):
    layout = {
        "parsing_res_list": [
            {
                "block_bbox": [1, 2, 30, 40],
                "block_label": "text",
                "block_content": "正文",
                "block_order": 1,
            }
        ]
    }
    body = json.dumps(
        {
            "result": {
                "layoutParsingResults": [
                    {"markdown": {"text": "正文"}, "prunedResult": layout}
                ]
            }
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        paddle_ocr.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(
            text=body, raise_for_status=lambda: None
        ),
    )

    assert paddle_ocr.download("https://example.test/result.jsonl") == [
        {"markdown": "正文", "layout": layout}
    ]


def test_ensure_mds_saves_layout_next_to_markdown(monkeypatch, tmp_path):
    cache_dir = tmp_path / "paper_paddle"
    layout = {"parsing_res_list": [{"block_label": "text"}]}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paddle_ocr, "_cache_dir", lambda pdf: str(cache_dir))
    monkeypatch.setattr(paddle_ocr, "submit", lambda pdf: "job-1")
    monkeypatch.setattr(paddle_ocr, "wait", lambda job_id: "result-url")
    monkeypatch.setattr(
        paddle_ocr,
        "download",
        lambda url: [{"markdown": "正文", "layout": layout}],
    )

    assert paddle_ocr.ensure_mds("paper.pdf", force=True) == 1
    assert (cache_dir / "doc_000.md").read_text(encoding="utf-8") == "正文"
    assert json.loads((cache_dir / "doc_000.json").read_text(encoding="utf-8")) == layout
