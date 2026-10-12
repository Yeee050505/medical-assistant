import hashlib
import math
import random
from functools import lru_cache
from typing import Protocol

from app.core.config import settings

_STOPWORDS = set("的了是在和有我你他她它们这那吗呢啊吧请问一下可以需要什么怎么因为所以但是而且如果")


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens: list[str] = []
    word = ""
    cjk_run: list[str] = []

    def flush_word() -> None:
        nonlocal word
        if word:
            tokens.append(word)
            word = ""

    def flush_cjk() -> None:
        for i, ch in enumerate(cjk_run):
            tokens.append(ch)
            if i + 1 < len(cjk_run):
                tokens.append(cjk_run[i] + cjk_run[i + 1])
        cjk_run.clear()

    for ch in text:
        if ch.isascii():
            flush_cjk()
            if ch.isalnum():
                word += ch
            else:
                flush_word()
        else:
            flush_word()
            if ch.isalnum():
                cjk_run.append(ch)
            else:
                flush_cjk()
    flush_word()
    flush_cjk()
    return tokens


@lru_cache(maxsize=4096)
def _unit_vec(token: str, dim: int) -> tuple[float, ...]:
    seed = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbedding:
    """词袋伪向量：token 的确定性 hash 单位向量加权求和后归一化，共词越多余弦越高。"""

    name = "mock"

    def __init__(self) -> None:
        self.dim = settings.embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            acc = [0.0] * self.dim
            weight_sum = 0.0
            for token in _tokenize(text):
                w = 0.15 if token in _STOPWORDS else 1.0
                if w <= 0:
                    continue
                weight_sum += w
                unit = _unit_vec(token, self.dim)
                for i, v in enumerate(unit):
                    acc[i] += w * v
            norm = math.sqrt(sum(x * x for x in acc))
            if norm < 1e-9:
                acc[0] = 1.0
            else:
                acc = [x / norm for x in acc]
            out.append(acc)
        return out


class OpenAICompatEmbedding:
    """OpenAI 兼容 /embeddings 接口（智谱 / 通义 / 百川等均兼容）。"""

    name = "openai_compat"

    def __init__(self) -> None:
        self.base_url = settings.embedding_base_url.rstrip("/")
        self.api_key = settings.embedding_api_key
        self.model = settings.embedding_model
        self._dim = settings.embedding_dim
        self._reported_dim: int | None = None

    @property
    def dim(self) -> int:
        return self._reported_dim or self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        vectors = [d["embedding"] for d in data]
        if vectors and self._reported_dim is None:
            self._reported_dim = len(vectors[0])
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "mock" or not settings.embedding_api_key:
        return MockEmbedding()
    return OpenAICompatEmbedding()
