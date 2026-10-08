"""临时脚本：直连 Redis 查看 pv:* 计数器，验证 PV 打点是否生效。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.task_store import redis_async


async def main() -> None:
    print("ping:", await redis_async.ping())
    keys = await redis_async.keys("pv:*")
    print("keys count:", len(keys))
    for k in sorted(keys):
        ttl = await redis_async.ttl(k)
        print(f"{k} = {await redis_async.get(k)}  (ttl={ttl}s)")
    await redis_async.aclose()


if __name__ == "__main__":
    asyncio.run(main())
