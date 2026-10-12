from collections.abc import Iterator
from typing import Protocol


class LLMProvider(Protocol):
    """大模型服务商统一接口：文本流式生成 + VL 图片解析。"""

    name: str

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        """messages: [{"role": "system|user|assistant", "content": str}]，返回增量文本。"""
        ...

    def parse_image(self, image_path: str) -> str:
        """解析内网图片，返回结构化文本。"""
        ...
