"""
认证横切设施：密码哈希（argon2）、JWT 编解码、当前用户依赖。

- JWT 无状态：HS256，sub=user_id，exp 默认 7 天，无黑名单无 refresh（本期无踢人需求）
- Cookie：HttpOnly + SameSite=Lax + Secure（按配置），浏览器自动携带，前端不碰 token
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import get_async_db
from app.models.users import Users

_password_hash = PasswordHash.recommended()  # argon2

ALGORITHM = "HS256"


# ---------- 密码 ----------

def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


# ---------- JWT ----------

def create_token(user: Users) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """验签并返回 payload；过期/篡改/格式错误一律返回 None。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )


# ---------- 当前用户依赖 ----------

async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Users:
    """必须登录：Cookie 中的 JWT 无效或用户不存在 → 401。"""
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    payload = decode_token(token) if token else None
    if payload is None:
        raise HTTPException(status_code=401, detail="请先登录")

    user = (await db.exec(select(Users).where(Users.id == int(payload["sub"])))).first()
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在或已失效")
    return user


async def get_current_user_optional(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Optional[Users]:
    """登录可选：未登录/凭证无效返回 None，不抛错。"""
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    payload = decode_token(token) if token else None
    if payload is None:
        return None
    return (await db.exec(select(Users).where(Users.id == int(payload["sub"])))).first()
