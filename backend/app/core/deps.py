from typing import Annotated

import jwt
import redis as redis_lib
from fastapi import Depends, Request

from app.core.config import settings
from app.core.response import forbidden, unauthorized
from app.core.security import decode_token
from app.models.user import ROLE_PERMISSIONS

_redis = redis_lib.Redis.from_url(settings.redis_url, socket_connect_timeout=2, protocol=2)

BLACKLIST_PREFIX = "token:bl:"


def _is_blacklisted(jti: str) -> bool:
    try:
        return _redis.exists(BLACKLIST_PREFIX + jti) > 0
    except redis_lib.RedisError:
        return False


def blacklist_token(payload: dict) -> None:
    try:
        ttl = max(payload.get("exp", 0) - int(__import__("time").time()), 1)
        _redis.setex(BLACKLIST_PREFIX + payload["jti"], ttl, "1")
    except redis_lib.RedisError:
        pass


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise unauthorized()
    token = auth[7:].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise unauthorized("JWT 令牌过期") from None
    except jwt.InvalidTokenError:
        raise unauthorized() from None

    if payload.get("type") != "access":
        raise unauthorized("refresh token 不可访问业务接口")
    if _is_blacklisted(payload.get("jti", "")):
        raise unauthorized("token 已登出失效")

    return payload


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_permission(permission: str):
    def checker(user: CurrentUser) -> dict:
        perms = ROLE_PERMISSIONS.get(user.get("role", ""), set())
        if permission not in perms:
            raise forbidden(f"缺少权限标识 {permission}")
        return user

    return checker
