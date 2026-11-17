from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates

from app.core.config import settings


def hk_datetime(value: str | None) -> str:
    if not value:
        return "—"
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y-%m-%d %H:%M")


def update_page_url(page: int, keyword: str = "", stage: str = "", change_kind: str = "") -> str:
    params: dict[str, str | int] = {"page": page}
    if keyword:
        params["keyword"] = keyword
    if stage:
        params["stage"] = stage
    if change_kind:
        params["change_kind"] = change_kind
    query = urlencode(params)
    return f"/updates?{query}" if query else "/updates"


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["site_base_url"] = settings.SITE_BASE_URL
templates.env.globals["update_page_url"] = update_page_url
templates.env.filters["hk_datetime"] = hk_datetime
