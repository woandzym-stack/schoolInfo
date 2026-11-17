"""用本机 Chrome 验证登录后的快讯管理页；需要本地 8081 服务已启动。"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.core.auth import create_token  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models.users import Users  # noqa: E402


async def main() -> None:
    admins = sorted(settings.admin_username_set)
    if not admins:
        raise RuntimeError("ADMIN_USERNAMES 为空，无法执行登录态验收")
    with Session(engine) as db:
        user = db.exec(select(Users).where(Users.username == admins[0])).first()
    if user is None:
        raise RuntimeError(f"管理员账号 {admins[0]} 在 users 表中不存在")

    output_dir = PROJECT_ROOT / "temp_workspace"
    output_dir.mkdir(exist_ok=True)
    page_errors: list[str] = []
    console_errors: list[str] = []
    api_errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            headless=True,
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        await context.add_cookies(
            [
                {
                    "name": settings.AUTH_COOKIE_NAME,
                    "value": create_token(user),
                    "url": "http://127.0.0.1:8081",
                    "httpOnly": True,
                    "secure": False,
                    "sameSite": "Lax",
                }
            ]
        )
        page = await context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)

        def collect_response(response) -> None:
            if response.status >= 500 and "/api/" in response.url:
                api_errors.append(f"{response.status} {response.url}")

        page.on("response", collect_response)
        await page.goto("http://127.0.0.1:8081/ui/admin/updates", wait_until="domcontentloaded")
        await page.get_by_role("heading", name="申请变化候选").wait_for(timeout=30000)
        await page.locator(".el-table__body tr").first.wait_for(timeout=30000)
        row_count = await page.locator(".el-table__body tr").count()
        await page.screenshot(path=str(output_dir / "update-admin-logged-in.png"), full_page=True)
        print("page heading:", await page.locator("h1").first.text_content())
        print("candidate table rows:", row_count)
        print("page errors:", page_errors)
        print("console errors:", console_errors)
        print("API errors:", api_errors)
        await browser.close()
    assert row_count > 0, "候选表没有渲染数据行"
    assert not page_errors and not console_errors and not api_errors, "浏览器运行时发现错误"


if __name__ == "__main__":
    asyncio.run(main())
