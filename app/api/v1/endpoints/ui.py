from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ui_router = APIRouter(tags=["UI"])

@ui_router.get("/prompt-studio", summary="Prompt 可视化工作台", include_in_schema=False)
async def serve_prompt_studio():
    """
    返回静态的前端 HTML 页面。
    注意：include_in_schema=False 可以让这个接口不在 Swagger UI (docs) 里显示，
    保持纯净的 API 文档。
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "index.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/index.html")

    return FileResponse(html_path)


@ui_router.get("/schools", summary="香港插班学校名录", include_in_schema=False)
async def serve_schools_directory():
    """香港插班 · 学校名录展示页面"""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "schools.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/schools.html")

    return FileResponse(html_path)


@ui_router.get("/subscriptions", summary="我的订阅", include_in_schema=False)
async def serve_subscriptions():
    """我的订阅页面（登录态由前端探测 /auth/me 判定）"""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "subscriptions.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/subscriptions.html")

    return FileResponse(html_path)