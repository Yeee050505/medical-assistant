import logging

from app.core.config import settings
from app.services.llm.factory import get_provider
from app.services.rag.embeddings import get_embedding_provider
from app.services.rag.store import search_points

logger = logging.getLogger(__name__)


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
    """在线链路：query 改写 → 向量召回 → 返回 [{docId, drugName, chunkContent, score}]。"""
    top_k = top_k or settings.rag_top_k
    try:
        rewritten = _rewrite(query, history)
        vector = get_embedding_provider().embed([rewritten])[0]
        points = search_points(vector, top_k)
        return [
            {
                "docId": p.payload.get("doc_id", ""),
                "drugName": p.payload.get("drug_name", ""),
                "chunkContent": p.payload.get("text", ""),
                "score": round(float(p.score), 4),
            }
            for p in points
            if p.payload and float(p.score) >= settings.rag_min_score
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG 检索失败，降级返回空: %s", exc)
        return []
