import jwt
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, blacklist_token, get_current_user
from app.core.response import bad_request, success, unauthorized
from app.core.security import create_token, decode_token, verify_password
from app.models.user import ROLE_PERMISSIONS, SysUser

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str


class RefreshBody(BaseModel):
    refreshToken: str


def _token_pair(user: SysUser) -> dict:
    access, expire_in = create_token(user.id, user.username, user.role, "access")
    refresh, _ = create_token(user.id, user.username, user.role, "refresh")
    return {
        "token": access,
        "refreshToken": refresh,
        "expireIn": expire_in,
        "role": user.role,
        "userId": user.id,
    }


@router.post("/login")
def login(request: Request, body: LoginBody, db: Session = Depends(get_db)):
    user = db.execute(select(SysUser).where(SysUser.username == body.username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise unauthorized("用户名或密码错误")
    if user.status != 1:
        raise unauthorized("账号已禁用")
    return success(request, _token_pair(user))


@router.get("/info")
def user_info(request: Request, user: CurrentUser):
    return success(
        request,
        {
            "userId": int(user["sub"]),
            "username": user["username"],
            "role": user["role"],
            "permissions": sorted(ROLE_PERMISSIONS.get(user["role"], set())),
        },
    )


@router.post("/refresh")
def refresh(request: Request, body: RefreshBody, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refreshToken)
    except jwt.InvalidTokenError:
        raise bad_request("refreshToken 无效或已过期") from None
    if payload.get("type") != "refresh":
        raise bad_request("refreshToken 类型错误")
    if _blacklisted(payload):
        raise bad_request("refreshToken 已失效")

    user = db.get(SysUser, int(payload["sub"]))
    if user is None or user.status != 1:
        raise unauthorized("用户不存在或已禁用")
    return success(request, _token_pair(user))


@router.post("/logout")
def logout(request: Request, user: dict = Depends(get_current_user)):
    blacklist_token(user)
    return success(request, {"success": True})


def _blacklisted(payload: dict) -> bool:
    from app.core.deps import _is_blacklisted

    return _is_blacklisted(payload.get("jti", ""))
