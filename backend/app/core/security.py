import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(
    user_id: int,
    username: str,
    role: str,
    token_type: str = "access",
) -> tuple[str, int]:
    """返回 (token, 过期秒数)。token_type: access / refresh"""
    now = datetime.now(UTC)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.jwt_expire_minutes)
        ttl = settings.jwt_expire_minutes * 60
    else:
        expire = now + timedelta(days=settings.jwt_refresh_expire_days)
        ttl = settings.jwt_refresh_expire_days * 86400
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_token(token: str) -> dict:
    """校验签名与有效期，返回 payload；无效时抛 jwt 异常。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
