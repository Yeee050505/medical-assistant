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
