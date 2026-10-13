"""Locust 压测场景：登录用户混合负载（问诊 / 知识库检索 / 健康检查）。

用法（需后端运行于 8000，且临时放大 RATE_LIMIT_QPS）：
    locust -f locustfile.py --headless -u 50 -r 10 -t 60s --csv=results/locust
"""
from locust import HttpUser, between, task

BASE = "/api/v1"


class MedicalUser(HttpUser):
    wait_time = between(0.2, 0.8)

    def on_start(self):
        r = self.client.post(
            f"{BASE}/auth/login",
            json={"username": "admin", "password": "Admin@123"},
            timeout=10,
        )
        if r.status_code == 200:
            self.headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}
            sess = self.client.post(
                f"{BASE}/chat/session/create",
                json={"userDesc": "压测初始化会话"},
                headers=self.headers,
                timeout=10,
            )
            self.session_id = (
                sess.json()["data"]["sessionId"] if sess.status_code == 200 else None
            )
        else:
            self.headers = {}
            self.session_id = None

    @task(3)
    def chat_message(self):
        if not self.session_id:
            return
        self.client.post(
            f"{BASE}/chat/session/{self.session_id}/message",
            json={"userDesc": "最近有点嗓子不舒服，需要吃什么药"},
            headers=self.headers,
            timeout=30,
        )

    @task(2)
    def rag_search(self):
        self.client.post(
            f"{BASE}/rag/search/test",
            json={"query": "阿莫西林有什么禁忌", "topK": 5},
            headers=self.headers,
            timeout=10,
        )

    @task(1)
    def health(self):
        self.client.get(f"{BASE}/health", timeout=5)

    @task(1)
    def user_info(self):
        self.client.get(f"{BASE}/auth/info", headers=self.headers, timeout=5)
