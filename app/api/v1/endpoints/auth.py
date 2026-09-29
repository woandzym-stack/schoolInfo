from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import (
    clear_auth_cookie,
    get_current_user,
    set_auth_cookie,
)
from app.core.config import settings
from app.core.db import get_async_db
from app.core.rate_limit import get_client_ip
from app.models.users import Users
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, UserOut
from app.schemas.response import SingleResponse
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=SingleResponse, summary="注册（成功即登录）")
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """
    用户名 + 密码 + 邮箱注册。

    - 按 IP 固定窗口限流 5 次/天（本期邮箱不验证，防批量小号）
    - 密码须 8-64 位且同时含字母和数字；用户名重复报 400
    - 注册成功直接种 JWT Cookie（注册即登录），注册 IP 入库供滥用追溯
    """
    ip = get_client_ip(request)
    if settings.RUN_MODE=="prod": 
        await auth_service.check_register_rate(ip)

    user, token = await auth_service.register(db, body.username, body.password, body.email, ip)
    set_auth_cookie(response, token)
    return SingleResponse(data=UserOut(id=user.id, username=user.username, email=user.email))


@router.post("/login", response_model=SingleResponse, summary="登录")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """
    用户名 + 密码登录，成功种 JWT Cookie。

    - 验密前执行双闸限流：IP 10 次/分 + 同账号失败 5 次锁 15 分钟（挡爆破与 argon2 资源消耗）
    - 失败提示统一为「用户名或密码错误」，不暴露账号是否存在
    """
    await auth_service.check_login_ip_rate(get_client_ip(request))

    user, token = await auth_service.login(db, body.username, body.password)
    set_auth_cookie(response, token)
    return SingleResponse(data=UserOut(id=user.id, username=user.username, email=user.email))


@router.post("/logout", response_model=SingleResponse, summary="登出")
async def logout(response: Response) -> SingleResponse:
    """清 Cookie 即完成（JWT 无状态，服务端无会话可销）。"""
    clear_auth_cookie(response)
    return SingleResponse(data=None)


@router.get("/me", response_model=SingleResponse, summary="当前登录用户")
async def me(user: Annotated[Users, Depends(get_current_user)]) -> SingleResponse:
    """前端页面加载时探测登录态用；未登录返回 401。"""
    return SingleResponse(data=UserOut(id=user.id, username=user.username, email=user.email))


@router.put("/password", response_model=SingleResponse, summary="修改密码")
async def change_password(
    body: ChangePasswordIn,
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """验证旧密码后设新密码；JWT 无状态，改密后旧 token 仍有效（本期无踢人需求）。"""
    await auth_service.change_password(db, user, body.old_password, body.new_password)
    return SingleResponse(data=None)
