from app.services.cache import cache_clear, cache_get, cache_json_get, cache_json_set, cache_set
from app.services.rag.embeddings import embed_texts

NS = "itest"


def test_cache_roundtrip_and_clear():
    cache_set(NS, "k1", "v1", ttl=60)
    assert cache_get(NS, "k1") == "v1"
    cache_json_set(NS, "k2", {"a": 1}, ttl=60)
    assert cache_json_get(NS, "k2") == {"a": 1}
    cache_clear(NS)
    assert cache_get(NS, "k1") is None
    assert cache_json_get(NS, "k2") is None


def test_cache_miss_returns_none():
    assert cache_get(NS, "never-set") is None


def test_embed_texts_cached_across_calls(monkeypatch):
    """同一文本第二次 embedding 走缓存，不再调用 provider。"""
    from app.services.rag import embeddings as emb_mod

    calls = {"n": 0}
    original = emb_mod.MockEmbedding.embed

    def counting_embed(self, texts):
        calls["n"] += 1
        return original(self, texts)

    monkeypatch.setattr(emb_mod.MockEmbedding, "embed", counting_embed)
    cache_clear("emb")

    text = f"缓存命中验证文本-{id(object())}"
    first = emb_embed_texts = embed_texts([text])
    second = embed_texts([text])
    assert calls["n"] == 1
    assert first == second
    cache_clear("emb")
    assert first == emb_embed_texts
