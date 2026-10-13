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
        line.split(":", 1)[1].strip() for line in body.splitlines() if line.startswith("event: ")
    ]
    assert "delta" in events and "done" in events
    delta_payloads = [
        json.loads(line.split(":", 1)[1]) for line in body.splitlines() if line.startswith("data: ")
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


def test_sse_emits_intent_event(client, auth_headers):
    """SSE 首事件为 intent。"""
    session_id = _create_session(client, auth_headers)
    with client.stream(
        "POST",
        f"{BASE}/chat/session/{session_id}/message",
        json={"userDesc": "嗓子有点疼，需要吃什么药"},
        headers={**auth_headers, "Accept": "text/event-stream"},
    ) as resp:
        body = "".join(resp.iter_text())
    events = [
        line.split(":", 1)[1].strip() for line in body.splitlines() if line.startswith("event: ")
    ]
    assert events[0] == "intent"
    assert "event: delta" in body and "event: done" in body


def test_chat_intent_skips_retrieval(client, auth_headers, monkeypatch):
    """问候语判 chat 意图，不触发 RAG 检索。"""
    calls = {"n": 0}
    import app.services.rag as rag

    original = rag.search_chunks

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("app.api.chat.search_chunks", counting)
    session_id = _create_session(client, auth_headers, desc="你好")
    assert calls["n"] == 0  # chat 意图，create 也跳过检索
    r = client.post(
        f"{BASE}/chat/session/{session_id}/message",
        json={"userDesc": "谢谢"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["intent"] == "chat"
    assert calls["n"] == 0  # 第二条消息未触发检索


def test_hot_topic_hit_skips_llm(client, auth_headers, monkeypatch):
    """命中热点词条：返回预置回答，不触发 LLM 生成。"""
    from app.core.database import SessionLocal
    from app.models.hot_topic import HotTopic
    from app.services.hot_cache import invalidate_topics

    with SessionLocal() as db:
        row = HotTopic(
            title="测试热点",
            keywords='["pytest专属关键词xyz"]',
            answer="这是预置的热点测试回答内容。",
            priority=999,
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        invalidate_topics()

    llm_calls = {"n": 0}
    from app.services.llm.factory import get_provider

    provider = get_provider()
    original = provider.stream_chat

    def counting_stream(messages):
        llm_calls["n"] += 1
        return original(messages)

    monkeypatch.setattr(provider, "stream_chat", counting_stream)
    try:
        session_id = _create_session(client, auth_headers)
        with client.stream(
            "POST",
            f"{BASE}/chat/session/{session_id}/message",
            json={"userDesc": "pytest专属关键词xyz怎么办"},
            headers={**auth_headers, "Accept": "text/event-stream"},
        ) as resp:
            body = "".join(resp.iter_text())
        assert "event: hot" in body
        assert "预置的热点测试回答" in body
        assert llm_calls["n"] == 0
    finally:
        with SessionLocal() as db:
            db.delete(db.get(HotTopic, row.id))
            db.commit()
            invalidate_topics()


def test_create_returns_intent_field(client, auth_headers):
    r = client.post(
        f"{BASE}/chat/session/create",
        json={"userDesc": "你好"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["intent"] == "chat"
    assert data["hotTitle"] == ""
