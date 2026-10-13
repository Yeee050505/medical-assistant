import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.services.rag.embeddings import get_embedding_provider

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, timeout=3)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def ensure_collection() -> str:
    name = settings.qdrant_collection
    dim = get_embedding_provider().dim
    client = _get_client()
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        client.create_payload_index(
            name, "doc_id", field_schema=PayloadSchemaType.KEYWORD
        )
        client.create_payload_index(name, "enabled", field_schema=PayloadSchemaType.BOOL)
    return name


def delete_doc_points(doc_id: str) -> None:
    name = ensure_collection()
    _get_client().delete(
        collection_name=name,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )


def upsert_chunks(
    doc_id: str, drug_name: str, texts: list[str], vectors: list[list[float]]
) -> None:
    name = ensure_collection()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "doc_id": doc_id,
                "drug_name": drug_name,
                "chunk_index": i,
                "text": text,
                "enabled": True,
            },
        )
        for i, (text, vec) in enumerate(zip(texts, vectors, strict=True))
    ]
    _get_client().upsert(collection_name=name, points=points)


def set_doc_enabled(doc_id: str, enabled: bool) -> None:
    name = ensure_collection()
    _get_client().set_payload(
        collection_name=name,
        payload={"enabled": enabled},
        points=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )


def search_points(vector: list[float], top_k: int) -> list:
    name = ensure_collection()
    resp = _get_client().query_points(
        collection_name=name,
        query=vector,
        limit=top_k,
        query_filter=Filter(must=[FieldCondition(key="enabled", match=MatchValue(value=True))]),
        with_payload=True,
    )
    return resp.points
