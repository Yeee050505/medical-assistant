import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from app.services.rag.bm25 import invalidate  # noqa: E402
from app.services.rag.store import delete_doc_points  # noqa: E402
from rag_eval import EVAL_CASES, EVAL_DOCS, evaluate, ingest_eval_docs  # noqa: E402

SAMPLE = EVAL_CASES[:5]


@pytest.fixture(scope="module", autouse=True)
def _eval_env():
    """评估语料：ingest 内置样例，结束后清理。"""
    from app.services.cache import cache_clear

    ingest_eval_docs()
    invalidate()
    cache_clear("rag")
    yield
    for doc_id, _, _ in EVAL_DOCS:
        try:
            delete_doc_points(doc_id)
        except Exception:  # noqa: BLE001
            pass
    invalidate()
    cache_clear("rag")


def test_rag_recall_gate():
    """检索质量门禁：样例用例 hybrid recall@5 ≥ 0.8（防检索退化）。"""
    report = evaluate(SAMPLE, k=5)
    misses = [r["query"] for r in report["rows"] if r["hybrid_rank"] == 0]
    assert report["hybrid_recall"] >= 0.8, f"recall@5 未达标，漏检: {misses}"


def test_rag_hybrid_not_worse_than_vector():
    """混合检索不应劣于纯向量召回（样例集上）。"""
    report = evaluate(EVAL_CASES, k=5)
    assert report["hybrid_recall"] >= report["vector_recall"] - 1e-9
