import hashlib
import json
import logging

from app.core.metrics import CACHE_OPS

logger = logging.getLogger(__name__)

_client = None
_client_failed = False


def _get():
    global _client, _client_failed
    if _client_failed:
        return None
    if _client is None:
        try:
            import redis

            _client = redis.Redis.from_url(
                settings_redis_url(), socket_connect_timeout=1, decode_responses=True
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("缓存 Redis 初始化失败，降级为无缓存: %s", exc)
            _client_failed = True
            return None
    return _client


def settings_redis_url() -> str:
    from app.core.config import settings

    return settings.redis_url


def make_key(*parts: str) -> str:
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(namespace: str, key: str) -> str | None:
    try:
        c = _get()
        value = c.get(f"cache:{namespace}:{key}") if c else None
        CACHE_OPS.labels(op="get", result="hit" if value else "miss").inc()
        return value
    except Exception as exc:  # noqa: BLE001
        logger.debug("缓存读取失败: %s", exc)
        CACHE_OPS.labels(op="get", result="error").inc()
        return None


def cache_set(namespace: str, key: str, value: str, ttl: int) -> None:
    try:
        c = _get()
        if c:
            c.setex(f"cache:{namespace}:{key}", ttl, value)
            CACHE_OPS.labels(op="set", result="ok").inc()
    except Exception as exc:  # noqa: BLE001
        logger.debug("缓存写入失败: %s", exc)
        CACHE_OPS.labels(op="set", result="error").inc()


def cache_clear(namespace: str) -> None:
    """按前缀清空命名空间（知识库变更时失效检索结果缓存）。"""
    try:
        c = _get()
        if not c:
            return
        cursor = 0
        while True:
            cursor, keys = c.scan(cursor=cursor, match=f"cache:{namespace}:*", count=200)
            if keys:
                c.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:  # noqa: BLE001
        logger.debug("缓存清理失败: %s", exc)


def cache_json_get(namespace: str, key: str):
    raw = cache_get(namespace, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def cache_json_set(namespace: str, key: str, value, ttl: int) -> None:
    cache_set(namespace, key, json.dumps(value, ensure_ascii=False), ttl)


def reset_client_for_tests() -> None:
    """测试隔离：重置模块级客户端状态。"""
    global _client, _client_failed
    _client = None
    _client_failed = False
