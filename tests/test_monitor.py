from conftest import BASE


def test_llm_usage_and_cost(client, auth_headers):
    r = client.post(
        f"{BASE}/chat/session/create",
        headers=auth_headers,
        json={"userDesc": "有点咳嗽，吃什么药好", "imageList": []},
    )
    assert r.status_code == 200
    trace_id = r.headers.get("X-Trace-Id")
    assert trace_id

    r = client.get(
        f"{BASE}/monitor/llm/cost",
        headers=auth_headers,
        params={"startDate": "2000-01-01", "endDate": "2100-01-01"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["totalCalls"] >= 1
    assert data["totalPromptTokens"] >= 1
    assert data["totalCompletionTokens"] >= 1
    assert data["totalCost"] >= 0
    assert any(t["apiType"] == "llm" for t in data["byApiType"])

    r = client.get(
        f"{BASE}/monitor/log",
        headers=auth_headers,
        params={"traceId": trace_id},
    )
    assert r.status_code == 200
    items = r.json()["data"]["list"]
    chat_hits = [i for i in items if i["path"] == "/api/v1/chat/session/create"]
    assert chat_hits, "审计日志应命中该 traceId 的问诊请求"
    assert chat_hits[0]["code"] == 200
    assert chat_hits[0]["userId"] is not None


def test_audit_log_records_requests(client, auth_headers):
    r = client.get(f"{BASE}/auth/info", headers=auth_headers)
    trace_id = r.headers.get("X-Trace-Id")
    r = client.get(
        f"{BASE}/monitor/log",
        headers=auth_headers,
        params={"traceId": trace_id},
    )
    items = r.json()["data"]["list"]
    assert any(i["path"] == "/api/v1/auth/info" for i in items)


def test_monitor_requires_auth(client):
    assert client.get(f"{BASE}/monitor/llm/cost").status_code == 401
    assert client.get(f"{BASE}/monitor/log").status_code == 401
