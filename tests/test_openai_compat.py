import json

import httpx
import pytest
from app.services.llm.openai_compat import OpenAICompatProvider


class _FakeStream:
    def __init__(self, lines: list[str]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter(self._lines)


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = payload
        self.requested = None

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _provider() -> OpenAICompatProvider:
    return OpenAICompatProvider()


def test_stream_chat_parses_sse(monkeypatch):
    lines = [
        ": keep-alive",
        "data: " + json.dumps({"choices": [{"delta": {"content": "你好"}}]}),
        "data: " + json.dumps({"choices": [{"delta": {}}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": "世界"}}]}),
        "data: [DONE]",
        "data: " + json.dumps({"choices": [{"delta": {"content": "不应出现"}}]}),
    ]
    captured = {}

    def fake_stream(method, url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        return _FakeStream(lines)

    monkeypatch.setattr(httpx, "stream", fake_stream)
    chunks = list(_provider().stream_chat([{"role": "user", "content": "hi"}]))
    assert chunks == ["你好", "世界"]
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["stream"] is True
    assert captured["headers"]["Authorization"].startswith("Bearer ")


def test_parse_image_builds_data_url(monkeypatch, tmp_path):
    img = tmp_path / "report.png"
    img.write_bytes(b"\x89PNG-fake-bytes")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        captured["url"] = url
        return _FakeResp({"choices": [{"message": {"content": "图片解析结果"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = _provider().parse_image(str(img))
    assert out == "图片解析结果"
    msg = captured["payload"]["messages"][0]
    image_url = msg["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert captured["payload"]["max_tokens"] == 1024


def test_rewrite_query_short_circuit_without_history():
    p = _provider()
    assert p.rewrite_query("头疼怎么办", None) == "头疼怎么办"
    assert p.rewrite_query("头疼怎么办", []) == "头疼怎么办"


def test_rewrite_query_with_history(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResp({"choices": [{"message": {"content": "  头痛症状用药咨询  "}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = _provider().rewrite_query("那这个呢", ["最近头痛", "吃什么药好"])
    assert out == "头痛症状用药咨询"
    user_msg = captured["payload"]["messages"][1]["content"]
    assert "最近头痛" in user_msg and "那这个呢" in user_msg
    assert captured["payload"]["temperature"] == 0.0
    assert captured["payload"]["max_tokens"] == 100


def test_stream_chat_propagates_http_error(monkeypatch):
    def fake_stream(method, url, headers=None, json=None, timeout=None):
        resp = _FakeStream([])

        def raise_for_status():
            raise httpx.HTTPStatusError(
                "500", request=httpx.Request("POST", url), response=httpx.Response(500)
            )

        resp.raise_for_status = raise_for_status
        return resp

    monkeypatch.setattr(httpx, "stream", fake_stream)
    with pytest.raises(httpx.HTTPStatusError):
        list(_provider().stream_chat([{"role": "user", "content": "x"}]))
