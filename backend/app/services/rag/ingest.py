from pathlib import Path

from app.core.config import settings
from app.services.rag.chunking import chunk_text
from app.services.rag.store import delete_doc_points, ensure_collection, upsert_chunks


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("pdfplumber 未安装：pip install pdfplumber") from exc
        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    raise ValueError(f"不支持的文档格式：{suffix}")


def ingest_file(doc_id: str, drug_name: str, file_path: str) -> int:
    """离线管线：解析 → 清洗 → 切片 → 向量化 → 写入 Qdrant，返回切片数。"""
    text = extract_text(file_path)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("未提取到有效文本内容")

    from app.services.rag.embeddings import embed_texts

    vectors = embed_texts(chunks)

    delete_doc_points(doc_id)
    ensure_collection()
    upsert_chunks(doc_id, drug_name, chunks, vectors)

    invalidate_retrieval()
    return len(chunks)


def invalidate_retrieval() -> None:
    """知识库变更后统一失效：BM25 索引 + RAG 结果缓存。"""
    from app.services.cache import cache_clear
    from app.services.rag.bm25 import invalidate

    invalidate()
    cache_clear("rag")


def save_upload(file_bytes: bytes, doc_id: str, suffix: str) -> str:
    target = settings.rag_doc_dir_path / f"{doc_id}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(file_bytes)
    return str(target)
