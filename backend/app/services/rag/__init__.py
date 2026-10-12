import logging

from app.core.config import settings
from app.services.llm.factory import get_provider
from app.services.rag.bm25 import _rrf_key, bm25_search
from app.services.rag.embeddings import get_embedding_provider
from app.services.rag.store import search_points

logger = logging.getLogger(__name__)

_CANDIDATES = 40
_RRF_K = 60


def _rewrite(query: str, history: list[str] | None) -> str:
    """在线链路：LLM 改写用户 query（口语→检索式），失败兜底原 query。"""
    if not history:
        return query
    try:
        rewritten = get_provider().rewrite_query(query, history)
        return rewritten.strip() or query
    except Exception as exc:  # noqa: BLE001
        logger.warning("query 改写失败，使用原始 query: %s", exc)
        return query


def search_chunks(
    query: str,
    top_k: int | None = None,
    history: list[str] | None = None,
) -> list[dict]:
    """混合检索：query 改写 → 向量召回(过相关性阈值) + BM25 关键词召回 → RRF 融合。"""
    top_k = top_k or settings.rag_top_k
    try:
        rewritten = _rewrite(query, history)

        vector = get_embedding_provider().embed([rewritten])[0]
        vec_points = search_points(vector, _CANDIDATES)
        vec_hits = [
            (p.payload, float(p.score))
            for p in vec_points
            if p.payload and float(p.score) >= settings.rag_min_score
        ]
        bm25_hits = bm25_search(rewritten, _CANDIDATES)

        fused: dict[tuple, dict] = {}

        def _add(payload: dict, rank: int, vec_score: float | None) -> None:
            key = _rrf_key(payload)
            entry = fused.setdefault(key, {"payload": payload, "rrf": 0.0, "vec_score": None})
            entry["rrf"] += 1.0 / (_RRF_K + rank)
            if vec_score is not None:
                entry["vec_score"] = vec_score

        for rank, (payload, score) in enumerate(vec_hits):
            _add(payload, rank, score)
        for rank, (payload, _score) in enumerate(bm25_hits):
            _add(payload, rank, None)

        ordered = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)[:top_k]
        return [
            {
                "docId": e["payload"].get("doc_id", ""),
                "drugName": e["payload"].get("drug_name", ""),
                "chunkContent": e["payload"].get("text", ""),
                "score": round(e["vec_score"] if e["vec_score"] is not None else e["rrf"], 4),
            }
            for e in ordered
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG 检索失败，降级返回空: %s", exc)
        return []
