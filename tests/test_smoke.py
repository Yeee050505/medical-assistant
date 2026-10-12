import io

BASE = "/api/v1"


def test_health(client):
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["code"] == 200
    assert r.json()["data"]["components"]["mysql"]["status"] == "up"


def test_login_and_info(client, auth_headers):
    r = client.get(f"{BASE}/auth/info", headers=auth_headers)
    data = r.json()["data"]
    assert data["username"] == "admin"
    assert "rag:write" in data["permissions"]


def test_login_wrong_password(client):
    r = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_token_required(client):
    r = client.get(f"{BASE}/auth/info")
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == 401
    assert "traceId" in body


def test_chat_session_flow(client, auth_headers):
    r = client.post(
        f"{BASE}/chat/session/create",
        headers=auth_headers,
        json={"userDesc": "嗓子干痒，轻微咳嗽", "imageList": []},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    session_id = data["sessionId"]
    assert session_id.startswith("sess-")
    assert "免责声明" in data["answer"] or "药品科普参考" in data["answer"]
    assert data["referenceDocs"] == []

    r = client.post(
        f"{BASE}/chat/session/{session_id}/message",
        headers={**auth_headers, "Accept": "text/event-stream"},
        json={"userDesc": "那这个药饭前吃还是饭后吃？", "imageList": []},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in r.text
    assert "event: done" in r.text

    r = client.post(
        f"{BASE}/chat/session/{session_id}/message",
        headers=auth_headers,
        json={"userDesc": "饭前还是饭后？", "imageList": []},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 200

    r = client.get(f"{BASE}/chat/session/list", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["data"]["list"]
    assert any(i["sessionId"] == session_id for i in items)

    r = client.get(f"{BASE}/chat/session/{session_id}", headers=auth_headers)
    messages = r.json()["data"]["messages"]
    assert len(messages) >= 4
    roles = [m["role"] for m in messages]
    assert roles[0] == "user" and "assistant" in roles


def test_file_upload(client, auth_headers):
    png = io.BytesIO(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    r = client.post(
        f"{BASE}/file/upload",
        headers=auth_headers,
        files={"file": ("t.png", png, "image/png")},
    )
    assert r.status_code == 200
    file_id = r.json()["data"]["fileId"]
    assert file_id.startswith("file-")


def test_logout_blacklist(client, auth_headers):
    r = client.post(f"{BASE}/auth/logout", headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f"{BASE}/auth/info", headers=auth_headers)
    assert r.status_code == 401
