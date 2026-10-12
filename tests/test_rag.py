import time

import jwt
import pytest
from conftest import BASE


@pytest.fixture(autouse=True)
def _fresh_collection():
    from app.services.rag.store import _get_client, ensure_collection

    client = _get_client()
    client.delete_collection(ensure_collection())
    ensure_collection()
    yield


SPEC_TEXT = """阿莫西林胶囊SPEC_TEXT

【适应症】适用于敏感菌所致的呼吸道感染、泌尿生殖道感染、皮肤软组织感染及伤寒等。

【用法用量】口服。成人一次0.5g，每8小时一次。小儿按体重一日20~40mg/kg，分3次服用。

【禁忌】对青霉素类药物过敏者禁用。哮喘、湿疹、枯草热、荨麻疹等过敏性疾病患者慎用。

【不良反应】常见恶心、呕吐、腹泻等胃肠道反应，偶见皮疹、药物热和哮喘。

【注意事项】服药期间禁止饮酒，肾功能不全者需减量，长期用药应定期检查肝肾功能。
"""


def test_rag_full_flow(client, auth_headers):
    r = client.post(
        f"{BASE}/rag/doc/upload",
        headers=auth_headers,
        files={"file": ("amosixin.txt", SPEC_TEXT.encode(), "text/plain")},
        data={"drugName": "阿莫西林", "version": "2024版"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "success", data
    doc_id, task_id = data["docId"], data["taskId"]

    r = client.get(f"{BASE}/rag/task/{task_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "success"

    r = client.get(f"{BASE}/rag/doc/list", headers=auth_headers, params={"drugName": "阿莫西林"})
    items = r.json()["data"]["list"]
    assert any(i["docId"] == doc_id and i["enabled"] for i in items)

    r = client.post(
        f"{BASE}/rag/search/test",
        headers=auth_headers,
        json={"query": "阿莫西林的禁忌", "topK": 5},
    )
    chunks = r.json()["data"]["list"]
    assert chunks, "检索应返回召回片段"
    assert chunks[0]["drugName"] == "阿莫西林"
    assert "禁忌" in chunks[0]["chunkContent"] or "青霉素" in chunks[0]["chunkContent"]

    r = client.post(
        f"{BASE}/chat/session/create",
        headers=auth_headers,
        json={"userDesc": "吃阿莫西林有什么禁忌？", "imageList": []},
    )
    refs = r.json()["data"]["referenceDocs"]
    assert refs and refs[0]["drugName"] == "阿莫西林"

    r = client.put(
        f"{BASE}/rag/doc/status",
        headers=auth_headers,
        json={"docId": doc_id, "status": "disable"},
    )
    assert r.json()["data"]["status"] == "disable"
    r = client.post(
        f"{BASE}/rag/search/test",
        headers=auth_headers,
        json={"query": "阿莫西林的禁忌", "topK": 5},
    )
    assert r.json()["data"]["list"] == [], "下线文档不应参与检索"

    r = client.put(
        f"{BASE}/rag/doc/status",
        headers=auth_headers,
        json={"docId": doc_id, "status": "enable"},
    )
    assert r.json()["data"]["status"] == "enable"


def test_rag_permission_denied(client):
    r = client.get(f"{BASE}/rag/doc/list")
    assert r.status_code == 401
    r = client.post(f"{BASE}/rag/search/test", json={"query": "x"})
    assert r.status_code == 401


def test_rate_limit_middleware():
    from app.core.config import settings
    from app.core.gateway import RateLimitMiddleware
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"code": 200}

    app.add_middleware(RateLimitMiddleware, qps=2)

    token = jwt.encode(
        {
            "sub": "rl-unit",
            "type": "access",
            "jti": "rl-unit-jti",
            "exp": int(time.time()) + 3600,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as c:
        codes = [c.get("/ping", headers=headers).status_code for _ in range(5)]

    assert codes[:2] == [200, 200]
    assert 429 in codes
    assert all(code in {200, 429} for code in codes)
