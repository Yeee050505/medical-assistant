import base64
import mimetypes
from collections.abc import Iterator
from pathlib import Path

import httpx

from app.core.config import settings


class OpenAICompatProvider:
    """OpenAI 兼容协议服务商（DeepSeek / 通义 / 智谱等均兼容），流式 + VL。"""

    def __init__(self) -> None:
        self.name = settings.llm_provider
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.vl_model = settings.vl_model or settings.llm_model
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True, "temperature": 0.3}
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                import json

                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta

    def parse_image(self, image_path: str) -> str:
        path = Path(image_path)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode()
        payload = {
            "model": self.vl_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "提取图片中的全部文字与结构化信息，输出纯文本。"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            "max_tokens": 1024,
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def rewrite_query(self, query: str, history: list[str] | None = None) -> str:
        if not history:
            return query
        sys_prompt = (
            "你是检索 query 改写助手。结合对话历史，将用户口语化的追问改写为"
            "独立、完整、含药品名称或症状关键词的检索 query，30 字以内，只输出改写结果。"
        )
        hist = "\n".join(f"- {h[:80]}" for h in history[-3:])
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"对话历史：\n{hist}\n本轮问题：{query}"},
            ],
            "max_tokens": 100,
            "temperature": 0.0,
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def classify_intent(self, query: str, history: list[str] | None = None) -> str:
        sys_prompt = (
            "你是意图分类器。判断用户问题属于哪一类，只输出一个词，不要输出其它内容。"
            "类别：qa=药品/症状/用药咨询；chat=问候闲聊；followup=对上文的追问；"
            "other=其它。"
        )
        hist = "\n".join(f"- {h[:60]}" for h in (history or [])[-2:])
        user_content = (
            f"对话历史：\n{hist}\n本轮问题：{query[:200]}" if hist else f"问题：{query[:200]}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 10,
            "temperature": 0.0,
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip().lower()
