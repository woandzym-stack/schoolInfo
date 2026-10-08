from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.pv_stats import incr_pv

ui_router = APIRouter(tags=["UI"])


@ui_router.get("/schools", summary="香港插班学校名录", include_in_schema=False)
async def serve_schools_directory():
    """香港插班 · 学校名录展示页面"""
    await incr_pv("schools")
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "schools.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/schools.html")

    return FileResponse(html_path)


@ui_router.get("/subscriptions", summary="我的订阅", include_in_schema=False)
async def serve_subscriptions():
    """我的订阅页面（登录态由前端探测 /auth/me 判定）"""
    await incr_pv("subscriptions")
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "subscriptions.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/subscriptions.html")

    return FileResponse(html_path)


@ui_router.get("/stats", summary="页面访问统计", include_in_schema=False)
async def serve_stats():
    """PV 统计仪表盘（数据接口 /api/v1/stats/visits 需登录，未登录由前端提示）。

    本页自身不打点，避免管理员自查污染统计。
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "stats.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/stats.html")

    return FileResponse(html_path)
