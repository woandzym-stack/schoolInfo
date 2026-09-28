"""
注册 / 登录 / 修改密码业务逻辑。

登录防爆破（方案 §5.2）：两道闸都在 argon2 验签之前执行——
- 按 IP 固定窗口限流（计数所有尝试，挡单源高频/撞库）
- 按账号失败计数（只在验密失败时 +1，≥5 次锁 15 分钟，成功清零，挡分散 IP 针对单账号的猜测）
"""
import time
from datetime import datetime

from fastapi import HTTPException
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import create_token, hash_password, verify_password
from app.core.rate_limit import check_rate_limit
from app.core.task_store import redis_async
from app.models.users import Users

_REGISTER_PER_DAY = 5        # 注册：每 IP 每天 5 次（防批量小号）
_LOGIN_PER_MINUTE = 10       # 登录：每 IP 每分钟 10 次
_LOGIN_FAIL_LIMIT = 5        # 登录：同账号连续失败 5 次锁定
_LOGIN_FAIL_TTL = 15 * 60    # 账号失败计数窗口：15 分钟

_FAIL_KEY = "rl:login:fail:{username}"


async def check_register_rate(ip: str) -> None:
    await check_rate_limit(
        [(f"rl:register:d:{ip}:{int(time.time() // 86400)}", 90000, _REGISTER_PER_DAY)],
        scene="注册接口",
    )


async def check_login_ip_rate(ip: str) -> None:
    await check_rate_limit(
        [(f"rl:login:m:{ip}:{int(time.time() // 60)}", 70, _LOGIN_PER_MINUTE)],
        scene="登录接口",
    )


async def _check_account_locked(username: str) -> None:
    """账号失败计数已达上限 → 429。Redis 异常时放行（fail-open，与限流策略一致）。"""
    try:
        n = await redis_async.get(_FAIL_KEY.format(username=username))
        if n is not None and int(n) >= _LOGIN_FAIL_LIMIT:
            raise HTTPException(status_code=429, detail="尝试次数过多，请 15 分钟后再试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败计数读取失败（放行本次请求）: {e}")


async def _record_login_fail(username: str) -> None:
    try:
        key = _FAIL_KEY.format(username=username)
        n = await redis_async.incr(key)
        if n == 1:
            await redis_async.expire(key, _LOGIN_FAIL_TTL)
    except Exception as e:
        logger.error(f"登录失败计数写入失败: {e}")


async def _clear_login_fail(username: str) -> None:
    try:
        await redis_async.delete(_FAIL_KEY.format(username=username))
    except Exception:
        pass


def _validate_password_strength(password: str) -> None:
    """密码须同时含字母和数字（长度已由 Schema 校验 8-64）。"""
    has_alpha = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_alpha and has_digit):
        raise HTTPException(status_code=400, detail="密码需同时包含字母和数字")


async def register(db: AsyncSession, username: str, password: str, email: str, ip: str) -> tuple[Users, str]:
    """注册新用户并签发 JWT（注册即登录）。"""
    _validate_password_strength(password)

    exists = (await db.exec(select(Users.id).where(Users.username == username))).first()
    if exists is not None:
        raise HTTPException(status_code=400, detail="用户名已被注册")

    now = datetime.now()
    user = Users(
        username=username,
        password_hash=hash_password(password),
        email=email,
        register_ip=ip,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()  # 拿到自增 id
    # 显式提交：依赖 teardown 的 commit 发生在响应发送之后（已验证），
    # 只有这里 commit 成功，端点才会返回成功响应并种 Cookie
    await db.commit()
    return user, create_token(user)


async def login(db: AsyncSession, username: str, password: str) -> tuple[Users, str]:
    """
    登录：账号锁检查 → 验密 → 失败计数/成功清零，返回用户与 JWT。
    失败提示统一为「用户名或密码错误」，不暴露账号是否存在。
    """
    await _check_account_locked(username)

    user = (await db.exec(select(Users).where(Users.username == username))).first()
    if user is None or not verify_password(password, user.password_hash):
        await _record_login_fail(username)
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    await _clear_login_fail(username)
    return user, create_token(user)


async def change_password(db: AsyncSession, user: Users, old_password: str, new_password: str) -> None:
    """修改密码：验旧密 → 强度校验 → 重哈希。"""
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    _validate_password_strength(new_password)

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now()
    db.add(user)
    await db.commit()  # 显式提交后才允许端点返回成功（见 register 注释）
