import os

os.environ.setdefault("RATE_LIMIT_QPS", "1000")

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

BASE = "/api/v1"


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
