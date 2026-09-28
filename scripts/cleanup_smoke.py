"""冒烟测试数据清理：删除测试用户及其订阅、Redis 登录失败计数。用完可删。"""
import asyncio

from sqlalchemy import delete

from app.core.db import AsyncSessionLocal
from app.core.task_store import redis_async
from app.models.subscriptions import Subscriptions
from app.models.users import Users


async def main() -> None:
    async with AsyncSessionLocal() as db:
        r1 = await db.exec(delete(Subscriptions).where(Subscriptions.user_id == 3))  # type: ignore[call-overload]
        r2 = await db.exec(delete(Users).where(Users.username == "smoketest01"))  # type: ignore[call-overload]
        await db.commit()
        print(f"subs_deleted={r1.rowcount} users_deleted={r2.rowcount}")
    await redis_async.delete("rl:login:fail:smoketest01")
    print("redis lock cleared")


asyncio.run(main())
