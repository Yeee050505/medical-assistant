import logging
import threading
import time

from qdrant_client.models import FieldCondition, Filter, MatchValue

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300
_lock = threading.Lock()
_index = None
_corpus: list[dict] = []
_loaded_at = 0.0
_dirty = True


def invalidate() -> None:
    """文档入库 / 启停变更后调用，下次检索时重建索引。"""
    global _dirty
    with _lock:
        _dirty = True


def _load() -> None:
    global _index, _corpus, _loaded_at, _dirty
    from qdrant_client import QdrantClient  # noqa: F401
    from rank_bm25 import BM25Okapi

    from app.services.rag.embeddings import _tokenize
    from app.services.rag.store import _get_client, ensure_collection

    name = ensure_collection()
    client = _get_client()
    payloads: list[dict] = []
    offset = None
    flt = Filter(must=[FieldCondition(key="enabled", match=MatchValue(value=True))])
    while True:
        records, offset = client.scroll(
            collection_name=name,
            scroll_filter=flt,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for rec in records:
            if rec.payload:
                payloads.append(rec.payload)
        if offset is None:
            break

    tokenized = [_tokenize(p.get("text", "")) for p in payloads]
    _index = BM25Okapi(tokenized) if tokenized else None
    _corpus = payloads
    _loaded_at = time.time()
    _dirty = False
    logger.info("BM25 索引重建完成：chunk 数=%d", len(payloads))


def _fresh() -> bool:
    return (not _dirty) and _index is not None and (time.time() - _loaded_at) < _TTL_SECONDS


def bm25_search(query: str, top_k: int = 40) -> list[tuple[dict, float]]:
    """BM25 关键词召回，返回 [(payload, score)]，score>0。"""
    with _lock:
        if not _fresh():
            try:
                _load()
            except Exception as exc:  # noqa: BLE001
                logger.warning("BM25 索引加载失败: %s", exc)
                return []
        index, corpus = _index, _corpus

    if index is None or not corpus:
        return []

    from app.services.rag.embeddings import _tokenize

    scores = index.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [(corpus[i], float(scores[i])) for i in ranked[:top_k] if scores[i] > 0]


def _rrf_key(payload: dict) -> tuple:
    return (payload.get("doc_id", ""), payload.get("chunk_index", -1))
