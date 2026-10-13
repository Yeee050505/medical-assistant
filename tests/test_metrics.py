BASE = "/api/v1"


def test_metrics_exposes_prometheus_format(client, auth_headers):
    r = client.get(f"{BASE}/monitor/metrics", headers=auth_headers)
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "rag_queries_total" in body or "llm_calls_total" in body


def test_metrics_requires_permission(client):
    r = client.get(f"{BASE}/monitor/metrics")
    assert r.status_code == 401
