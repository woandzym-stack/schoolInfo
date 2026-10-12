"""清空 Redis 中的 PV 统计数据（pv:* 前缀的所有 key）。

用于统计口径切换（加入扫描流量过滤）后丢弃脏历史数据，从干净数据重新累计。
只动 pv: 前缀，其他业务 key 不受影响。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.task_store import redis_async


async def main() -> None:
    keys = [key async for key in redis_async.scan_iter(match="pv:*", count=200)]
    if not keys:
        print("没有匹配的 pv:* key，无需清理")
        return

    print(f"将删除 {len(keys)} 个 key：")
    for key in sorted(keys):
        value = await redis_async.get(key)
        print(f"  DEL {key} (value={value})")

    await redis_async.delete(*keys)
    remaining = [key async for key in redis_async.scan_iter(match="pv:*", count=200)]
    print(f"\n已删除 {len(keys)} 个 key，剩余 pv:* key 数：{len(remaining)}")


if __name__ == "__main__":
    asyncio.run(main())
