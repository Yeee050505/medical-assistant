"""热点缓存：人工热点词表（MySQL）+ 自动积累（Redis 精确归一化匹配）。

命中后跳过 RAG 检索与 LLM 生成，直接返回预置/缓存回答；任何异常降级为未命中，
不影响主链路可用性。自动积累仅存 qa 类成功回答，TTL 可配置。
"""

import hashlib
import json
import logging
import re
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOPICS_NS = "hot_topics"  # Redis 人工词表快照命名空间
_AUTO_NS = "hotauto"  # Redis 自动积累命名空间
_TOPIC_MEM_TTL = 300  # 进程内人工词表缓存秒数

_PUNCT_RE = re.compile(r"[\s，。！？、；：" "''（）()【】\[\]<>《》,.!?;:~`@#$%^&*+=|/\\-]+")

_topics_cache: list[dict] = []
_topics_loaded_at: float = 0.0


def normalize_query(text: str) -> str:
    """归一化：小写 + 去空白/标点（自动积累 key 与人工匹配共用）。"""
    return _PUNCT_RE.sub("", (text or "").lower())


def _auto_key(query: str) -> str:
    return hashlib.md5(normalize_query(query).encode("utf-8")).hexdigest()


def _load_topics(db) -> list[dict]:
    """从 DB/Redis 快照加载启用中的人工热点词条。"""
    global _topics_cache, _topics_loaded_at
    now = time.monotonic()
    if _topics_cache and now - _topics_loaded_at < _TOPIC_MEM_TTL:
        return _topics_cache
    topics: list[dict] = []
    try:
        from sqlalchemy import select

        from app.models.hot_topic import HotTopic

        rows = db.execute(select(HotTopic).where(HotTopic.enabled.is_(True))).scalars()
        for r in rows:
            try:
                keywords = json.loads(r.keywords or "[]")
            except ValueError:
                keywords = []
            if not isinstance(keywords, list):
                continue
            topics.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "answer": r.answer,
                    "priority": r.priority,
                    "keywords": [normalize_query(str(k)) for k in keywords if str(k).strip()],
                }
            )
        topics.sort(key=lambda t: t["priority"], reverse=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("热点词表加载失败: %s", exc)
        return _topics_cache
    _topics_cache = topics
    _topics_loaded_at = now
    return topics


def invalidate_topics() -> None:
    """人工词表变更后清空进程内缓存（CRUD 接口调用）。"""
    global _topics_cache, _topics_loaded_at
    _topics_cache = []
    _topics_loaded_at = 0.0


def lookup_hot(user_query: str, db) -> dict | None:
    """查询热点：人工词表（关键词任一包含，priority 最高优先）→ 自动积累。

    返回 {"title", "answer", "source": "manual"|"auto"} 或 None。
    """
    if not settings.hot_cache_enabled:
        return None
    nq = normalize_query(user_query)
    if not nq:
        return None
    try:
        for topic in _load_topics(db):
            for kw in topic["keywords"]:
                if kw and kw in nq:
                    return {
                        "title": topic["title"],
                        "answer": topic["answer"],
                        "source": "manual",
                    }
        from app.services.cache import cache_get

        raw = cache_get(_AUTO_NS, _auto_key(user_query))
        if raw:
            payload = json.loads(raw)
            return {
                "title": payload.get("title", "常见问题"),
                "answer": payload.get("answer", ""),
                "source": "auto",
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("热点查询失败，降级走原链路: %s", exc)
    return None


def remember_answer(user_query: str, title: str, answer: str) -> None:
    """qa 链路成功后自动积累（精确归一化匹配，TTL 可配置）。"""
    if not settings.hot_cache_enabled or not settings.hot_auto_ttl_seconds:
        return
    nq = normalize_query(user_query)
    if len(nq) < 4 or not answer:
        return
    try:
        from app.services.cache import cache_set

        payload = json.dumps({"title": title[:30], "answer": answer}, ensure_ascii=False)
        cache_set(_AUTO_NS, _auto_key(user_query), payload, settings.hot_auto_ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.debug("热点自动积累失败: %s", exc)
