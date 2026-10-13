from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import SysUser

BASE = "/api/v1"


def _login(client, username="admin", password="Admin@123"):
    return client.post(f"{BASE}/auth/login", json={"username": username, "password": password})


def test_login_success(client):
    r = _login(client)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["token"] and data["refreshToken"]
    assert data["role"] == "admin"
    assert data["expireIn"] > 0


def test_login_wrong_password(client):
    r = _login(client, password="wrong-pass")
    assert r.status_code == 401
    assert r.json()["code"] == 401


def test_access_without_token(client):
    r = client.get(f"{BASE}/auth/info")
    assert r.status_code == 401


def test_non_admin_forbidden_from_monitor(client):
    """普通用户访问监控接口 → 403（RBAC 权限门禁）。"""
    with SessionLocal() as db:
        user = SysUser(
            username="it-user-perm",
            password_hash=hash_password("User@123"),
            role="user",
            status=1,
        )
        db.add(user)
        db.commit()
    try:
        r = _login(client, username="it-user-perm", password="User@123")
        assert r.status_code == 200
        token = r.json()["data"]["token"]
        resp = client.get(
            f"{BASE}/monitor/llm/cost", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
    finally:
        with SessionLocal() as db:
            row = db.query(SysUser).filter(SysUser.username == "it-user-perm").first()
            if row:
                db.delete(row)
                db.commit()


def test_refresh_issues_new_token_pair(client, auth_headers):
    r = _login(client)
    refresh = r.json()["data"]["refreshToken"]
    resp = client.post(f"{BASE}/auth/refresh", json={"refreshToken": refresh})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["token"] and data["token"] != r.json()["data"]["token"]


def test_logout_blacklists_access_token(client, auth_headers):
    """登出后旧 access token 立即失效（黑名单）。"""
    r = client.get(f"{BASE}/auth/info", headers=auth_headers)
    assert r.status_code == 200
    assert client.post(f"{BASE}/auth/logout", headers=auth_headers).status_code == 200
    after = client.get(f"{BASE}/auth/info", headers=auth_headers)
    assert after.status_code == 401
