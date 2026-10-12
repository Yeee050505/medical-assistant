import re
import time
from collections.abc import Iterator

_FILLERS = (
    "我想问一下",
    "我想问",
    "请问一下",
    "请问",
    "大夫",
    "医生",
    "帮我看看",
    "帮我看下",
    "那个",
    "就是说",
    "就是",
    "一下",
    "你好",
)


class MockProvider:
    """开发期 mock：不调用外部 API，返回固定科普文本并模拟流式。"""

    name = "mock"

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        question = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        text = (
            f"【模拟回答】关于“{question[:60]}”：\n"
            "1. 请严格遵照药品说明书的用法用量使用，不可自行增减剂量；\n"
            "2. 用药前请仔细阅读说明书中的禁忌、不良反应与注意事项；\n"
            "3. 若症状持续或加重，请及时前往正规医疗机构就诊。\n"
            "（当前为 mock 模式，未调用真实大模型 API，填入 API Key 后自动切换）"
        )
        for i in range(0, len(text), 10):
            time.sleep(0.03)
            yield text[i : i + 10]

    def parse_image(self, image_path: str) -> str:
        return f"【mock 图片解析】{image_path}：检验报告/患处图片解析文本（mock 模式占位）"

    def rewrite_query(self, query: str, history: list[str] | None = None) -> str:
        q = query.split("[图片解析]", 1)[0]
        for filler in _FILLERS:
            q = q.replace(filler, " ")
        q = re.sub(r"\s+", " ", q).strip()
        if history:
            ctx = re.sub(r"\s+", " ", history[-1]).strip()[:40]
            if ctx and ctx not in q:
                q = f"{ctx} {q}".strip()
        return q or query
