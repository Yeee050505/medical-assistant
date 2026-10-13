import json

import pytest
from app.core.database import SessionLocal
from app.models.hot_topic import HotTopic
from app.services.hot_cache import invalidate_topics, lookup_hot, normalize_query, remember_answer


@pytest.fixture(autouse=True)
def _hot_topics_isolated():
    """清空词表保证用例确定性，测试后恢复原有词条（保护 dev 种子数据）。"""
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.execute(select(HotTopic)).scalars().all()
        saved = [(r.title, r.keywords, r.answer, r.priority, r.enabled) for r in rows]
        for r in rows:
            db.delete(r)
        db.commit()
    invalidate_topics()
    yield
    with SessionLocal() as db:
        for title, keywords, answer, priority, enabled in saved:
            db.add(
                HotTopic(
                    title=title,
                    keywords=keywords,
                    answer=answer,
                    priority=priority,
                    enabled=enabled,
                )
            )
        db.commit()
    invalidate_topics()


def _add_topic(db, title, keywords, answer="预置回答内容", priority=0):
    row = HotTopic(
        title=title,
        keywords=json.dumps(keywords, ensure_ascii=False),
        answer=answer,
        priority=priority,
        enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_topics()
    return row


def test_normalize_query():
    assert normalize_query("  布洛芬，怎么吃？  ") == "布洛芬怎么吃"
    assert normalize_query("Hello, World!") == "helloworld"


def test_manual_keyword_hit():
    with SessionLocal() as db:
        row = _add_topic(db, "流感", ["奥司他韦", "达菲"], "流感科普回答", priority=10)
        try:
            hit = lookup_hot("流感吃奥司他韦有用吗", db)
            assert hit is not None
            assert hit["source"] == "manual"
            assert hit["title"] == "流感"
            assert hit["answer"] == "流感科普回答"
        finally:
            db.delete(row)
            db.commit()
            invalidate_topics()


def test_priority_wins():
    with SessionLocal() as db:
        low = _add_topic(db, "低", ["布洛芬"], "低优先级", priority=1)
        high = _add_topic(db, "高", ["退烧药"], "高优先级", priority=50)
        try:
            hit = lookup_hot("发烧了吃退烧药还是布洛芬", db)
            assert hit["title"] == "高"
        finally:
            db.delete(low)
            db.delete(high)
            db.commit()
            invalidate_topics()


def test_disabled_topic_skipped():
    with SessionLocal() as db:
        row = HotTopic(
            title="停用",
            keywords=json.dumps(["停用关键词"], ensure_ascii=False),
            answer="不该被命中",
            enabled=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        invalidate_topics()
        try:
            assert lookup_hot("停用关键词问题", db) is None
        finally:
            db.delete(row)
            db.commit()
            invalidate_topics()


def test_miss_returns_none():
    with SessionLocal() as db:
        assert lookup_hot("完全无关的问题内容", db) is None


def test_auto_accumulate_hit(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "hot_cache_enabled", True)
    monkeypatch.setattr(settings, "hot_auto_ttl_seconds", 3600)
    remember_answer("阿莫西林能和布洛芬一起吃吗", "联合用药", "不建议自行联用，请遵医嘱。")
    with SessionLocal() as db:
        hit = lookup_hot("阿莫西林能和布洛芬一起吃吗", db)
        assert hit is not None
        assert hit["source"] == "auto"
        assert "不建议自行联用" in hit["answer"]


def test_auto_skips_short_query():
    remember_answer("嗯", "短", "回答")
    with SessionLocal() as db:
        assert lookup_hot("嗯", db) is None


def test_disabled_cache(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "hot_cache_enabled", False)
    remember_answer("特定问题内容词组", "标题", "回答")
    with SessionLocal() as db:
        assert lookup_hot("特定问题内容词组", db) is None
