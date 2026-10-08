"""临时脚本：验证 get_pv_overview 聚合输出。"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pv_stats import get_pv_overview


async def main() -> None:
    overview = await get_pv_overview(days=7)
    print(json.dumps(overview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
