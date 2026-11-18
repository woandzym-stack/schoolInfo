"""本地 MySQL 申请快讯 HTTP 闭环验收；只清理带【本地验收】前缀的测试数据。

用法：
  poetry run python scripts/smoke_admission_updates.py
  poetry run python scripts/smoke_admission_updates.py --cleanup-only

要求：先执行 scripts/create_admission_updates.sql。不会采用或修改真实抓取候选。
"""
# ruff: noqa: E402
import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models.users import Users
from app.services.admission_update_service import HK_TZ

TEST_TITLE = "【本地验收】申请快讯测试，不是学校公告"


def cleanup() -> None:
    """物理清理本脚本创建的本地测试行，不触碰任何真实快讯或候选。"""
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "DELETE FROM admission_change_reviews WHERE update_id IN "
            "(SELECT id FROM admission_updates WHERE title LIKE '【本地验收】%%')"
        )
        conn.exec_driver_sql("DELETE FROM admission_updates WHERE title LIKE '【本地验收】%%'")
        remaining = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM admission_updates WHERE title LIKE '【本地验收】%%'"
        ).scalar()
    print(f"smoke rows remaining after cleanup: {remaining}")


def main(cleanup_only: bool = False) -> None:
    cleanup()
    if cleanup_only:
        return

    now = datetime.now()
    admin = Users(
        id=1,
        username="smoke_admin",
        password_hash="",
        email="smoke@example.com",
        register_ip="",
        created_at=now,
        updated_at=now,
    )

    async def smoke_user() -> Users:
        return admin

    original_admins = settings.ADMIN_USERNAMES
    app.dependency_overrides[get_current_user] = smoke_user
    settings.ADMIN_USERNAMES = "smoke_admin"
    update_id = None
    try:
        with TestClient(app) as client:
            detected_on = datetime.now(HK_TZ).date().isoformat()
            candidates = client.get(
                "/api/v1/admin/admission-changes",
                params={"page_size": 5, "detected_on": detected_on},
            )
            assert candidates.status_code == 200, candidates.text
            candidate_data = candidates.json()["data"]
            assert candidate_data["total"] > 0
            school_id = candidate_data["items"][0]["school"]["id"]
            print(f"today candidates: {candidate_data['total']} | school_id: {school_id}")

            payload = {
                "school_id": school_id,
                "change_kind": "deadline_changed",
                "title": TEST_TITLE,
                "summary": "仅验证本地发布链路，不代表任何学校安排。",
                "sources": [
                    {
                        "name": "本地测试来源",
                        "url": "https://example.com/smoke",
                        "support": "仅验证 JSON 与来源展示",
                    }
                ],
                "verified_at": f"{detected_on}T12:00:00+08:00",
            }
            created_resp = client.post("/api/v1/admin/updates", json=payload)
            assert created_resp.status_code == 200, created_resp.text
            created = created_resp.json()["data"]
            update_id = created["id"]
            assert created["status"] == "draft"
            assert created["sources"][0]["url"] == "https://example.com/smoke"
            assert client.get(f"/updates/{update_id}").status_code == 404

            published_resp = client.post(f"/api/v1/admin/updates/{update_id}/publish")
            assert published_resp.status_code == 200, published_resp.text
            first_time = published_resp.json()["data"]["first_published_at"]
            assert client.get(f"/updates/{update_id}").status_code == 200
            assert client.get(f"/api/v1/updates/{update_id}").json()["data"]["id"] == update_id
            assert f"/updates/{update_id}</loc>" in client.get("/sitemap.xml").text
            print("create draft -> publish -> HTML/API/sitemap: OK")

            payload.update(
                {
                    "title": TEST_TITLE + "（已修改）",
                    "summary": "本地修改验收",
                }
            )
            payload.pop("school_id")
            edited = client.put(f"/api/v1/admin/updates/{update_id}", json=payload)
            assert edited.status_code == 200, edited.text
            deleted = client.post(f"/api/v1/admin/updates/{update_id}/delete", json={"reason": "本地验收清理"})
            assert deleted.status_code == 200, deleted.text
            assert client.get(f"/updates/{update_id}").status_code == 404
            assert f"/updates/{update_id}</loc>" not in client.get("/sitemap.xml").text
            restored = client.post(f"/api/v1/admin/updates/{update_id}/restore")
            assert restored.status_code == 200 and restored.json()["data"]["status"] == "draft"
            republished = client.post(f"/api/v1/admin/updates/{update_id}/publish")
            assert republished.status_code == 200
            assert republished.json()["data"]["first_published_at"] == first_time
            print("edit -> delete -> 404/sitemap removal -> restore -> republish: OK")
    finally:
        app.dependency_overrides.clear()
        settings.ADMIN_USERNAMES = original_admins
        cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    main(cleanup_only=args.cleanup_only)
