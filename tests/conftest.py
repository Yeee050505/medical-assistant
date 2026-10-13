import os

os.environ.setdefault("RATE_LIMIT_QPS", "1000")
os.environ.setdefault("LOG_JSON", "false")

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

BASE = "/api/v1"


@pytest.fixture(autouse=True)
def _clean_rag_cache():
    """每个测试前清空 RAG 结果缓存与热点自动积累，防止跨测试用例污染。"""
    from app.services.cache import cache_clear
    from app.services.hot_cache import invalidate_topics

    cache_clear("rag")
    cache_clear("hotauto")
    invalidate_topics()
    yield
    cache_clear("rag")
    cache_clear("hotauto")
    invalidate_topics()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    r = client.post(
        f"{BASE}/auth/login",
        json={"username": "admin", "password": "Admin@123"},
    )
    assert r.status_code == 200
    token = r.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
