import json

BASE = "/api/v1"


def _create_session(client, auth_headers, desc="最近嗓子干痒，有点咳嗽"):
    r = client.post(
        f"{BASE}/chat/session/create",
        json={"userDesc": desc},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["sessionId"]


def test_sse_stream_emits_delta_and_done(client, auth_headers):
    session_id = _create_session(client, auth_headers)
    with client.stream(
        "POST",
        f"{BASE}/chat/session/{session_id}/message",
        json={"userDesc": "有点低烧怎么办"},
        headers={**auth_headers, "Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "event: delta" in body
    assert "event: done" in body
    events = [
        line.split(":", 1)[1].strip()
        for line in body.splitlines()
        if line.startswith("event: ")
    ]
    assert "delta" in events and "done" in events
    delta_payloads = [
        json.loads(line.split(":", 1)[1])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert any(p.get("content") for p in delta_payloads)


def test_answer_contains_disclaimer(client, auth_headers):
    """非流式回答必须附带免责声明。"""
    session_id = _create_session(client, auth_headers)
    r = client.post(
        f"{BASE}/chat/session/{session_id}/message",
        json={"userDesc": "布洛芬怎么吃"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    answer = r.json()["data"]["answer"]
    assert "不能替代" in answer or "仅供参考" in answer


def test_message_on_missing_session_404(client, auth_headers):
    r = client.post(
        f"{BASE}/chat/session/sess-not-exist-xyz/message",
        json={"userDesc": "测试"},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_message_requires_auth(client):
    session_id_hint = "sess-any"
    r = client.post(
        f"{BASE}/chat/session/{session_id_hint}/message",
        json={"userDesc": "测试"},
    )
    assert r.status_code == 401
