import asyncio
import json
from datetime import datetime
from xml.etree import ElementTree

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.core.auth import get_admin_user
from app.core.config import settings
from app.core.db import get_async_db
from app.core.templates import templates
from app.main import app
from app.models.admission_change_reviews import AdmissionChangeReviews
from app.models.admission_updates import AdmissionUpdates
from app.models.users import Users
from app.schemas.admission_update import AdmissionUpdateContent
from app.services import admission_update_service


def valid_content() -> AdmissionUpdateContent:
    return AdmissionUpdateContent(
        title="示例中學延期",
        summary="截止延期一週",
        sources=[{"name": "學校公告", "url": "https://example.com/notice", "support": "截止日期"}],
        verified_at="2026-11-16T12:00:00+08:00",
    )


def test_schema_publish_validation_and_json_serialization():
    payload = valid_content()
    assert payload.publish_errors() == []
    # 来源对应信息（support）可空，来源名称仍必填
    no_support = valid_content()
    no_support.sources[0].support = ""
    assert no_support.publish_errors() == []
    no_name = valid_content()
    no_name.sources[0].name = ""
    assert no_name.publish_errors() == ["每个官方来源都需要填写来源名称"]
    stored = payload.sources_for_storage()
    assert stored == [{"name": "學校公告", "url": "https://example.com/notice", "support": "截止日期"}]
    assert json.loads(json.dumps(stored)) == stored
    assert AdmissionUpdateContent().publish_errors() == [
        "标题不能为空",
        "一句话重点不能为空",
        "至少需要一个官方来源",
        "本站核实时间不能为空",
    ]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/a", "https://user:pass@example.com/a"])
def test_source_rejects_unsafe_url(url):
    with pytest.raises(ValidationError):
        AdmissionUpdateContent(sources=[{"name": "bad", "url": url, "support": "bad"}])


def test_mysql_ddl_contains_expected_columns_and_json_type():
    update_ddl = str(CreateTable(AdmissionUpdates.__table__).compile(dialect=mysql.dialect()))
    review_ddl = str(CreateTable(AdmissionChangeReviews.__table__).compile(dialect=mysql.dialect()))
    assert "sources_json JSON NOT NULL" in update_ddl
    assert "official_published_on DATE" in update_ddl
    assert "status VARCHAR(20) NOT NULL" in update_ddl
    assert "change_id INTEGER NOT NULL" in review_ddl
    assert "PRIMARY KEY (change_id)" in review_ddl


def test_public_templates_escape_editor_content():
    school = {"id": 1, "name": "示例中學", "stage": "secondary", "district": "九龍城區", "url": None}
    item = {
        "id": 1,
        "change_kind": "other",
        "change_kind_label": "其他变化",
        "title": "<script>alert(1)</script>",
        "summary": "摘要",
        "sources": [{"name": "公告", "url": "https://example.com", "support": "<img src=x onerror=alert(1)>"}],
        "verified_at": "2026-11-16T12:00:00+08:00",
        "first_published_at": "2026-11-16T12:00:00+08:00",
        "content_modified_at": "2026-11-16T12:00:00+08:00",
        "school": school,
    }
    detail_html = templates.get_template("updates/detail.html").render(
        title=item["title"],
        description="摘要",
        canonical="https://school.ddup.app/updates/1",
        robots="index,follow",
        update=item,
        json_ld={"headline": item["title"]},
    )
    assert "<script>alert(1)</script>" not in detail_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail_html
    assert "<img src=x onerror=alert(1)>" not in detail_html
    list_html = templates.get_template("updates/list.html").render(
        title="插班动态",
        description="摘要",
        canonical="https://school.ddup.app/updates",
        robots="index,follow",
        data={"items": [item], "page": 1, "page_size": 20, "total": 1, "pages": 1},
        keyword="",
        stage="secondary",
        filters={},
        filter_defs=[],
        filter_options={},
        filtered=False,
        page_numbers=[1],
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in list_html


@pytest.fixture
def client():
    async def fake_db():
        yield object()

    app.dependency_overrides[get_async_db] = fake_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_public_html_404_and_json_404(client, monkeypatch):
    async def missing(*args, **kwargs):
        return None

    monkeypatch.setattr(admission_update_service, "get_public_update", missing)
    html_response = client.get("/updates/999999")
    assert html_response.status_code == 404
    assert "text/html" in html_response.headers["content-type"]
    assert "找不到这条动态" in html_response.text
    api_response = client.get("/api/v1/updates/999999")
    assert api_response.status_code == 404
    assert api_response.json()["errCode"] == 404


def test_admin_requires_login_and_whitelist(client):
    anonymous = client.get("/api/v1/admin/admission-changes")
    assert anonymous.status_code == 401

    async def normal_user():
        now = datetime.now()
        return Users(
            id=1,
            username="ordinary",
            password_hash="",
            email="ordinary@example.com",
            register_ip="",
            created_at=now,
            updated_at=now,
        )

    from app.core.auth import get_current_user

    app.dependency_overrides[get_current_user] = normal_user
    ordinary = client.get("/api/v1/admin/updates")
    assert ordinary.status_code == 403


def test_admin_dependency_checks_current_whitelist():
    now = datetime.now()
    user = Users(
        id=1,
        username="editor",
        password_hash="",
        email="editor@example.com",
        register_ip="",
        created_at=now,
        updated_at=now,
    )
    original = settings.ADMIN_USERNAMES
    try:
        settings.ADMIN_USERNAMES = ""
        with pytest.raises(HTTPException) as denied:
            asyncio.run(get_admin_user(user))
        assert denied.value.status_code == 403
        settings.ADMIN_USERNAMES = "other, editor"
        assert asyncio.run(get_admin_user(user)) is user
    finally:
        settings.ADMIN_USERNAMES = original


def test_auth_me_exposes_admin_navigation_flag(client):
    from app.core.auth import get_current_user

    async def editor_user():
        now = datetime.now()
        return Users(
            id=1,
            username="editor",
            password_hash="",
            email="editor@example.com",
            register_ip="",
            created_at=now,
            updated_at=now,
        )

    original = settings.ADMIN_USERNAMES
    app.dependency_overrides[get_current_user] = editor_user
    try:
        settings.ADMIN_USERNAMES = "editor"
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["data"]["is_admin"] is True
        settings.ADMIN_USERNAMES = "other"
        response = client.get("/api/v1/auth/me")
        assert response.json()["data"]["is_admin"] is False
    finally:
        settings.ADMIN_USERNAMES = original


def test_sitemap_uses_only_public_service_rows(client, monkeypatch):
    async def entries(db):
        return [{"id": 7, "lastmod": "2026-11-16T12:00:00+08:00"}]

    monkeypatch.setattr(admission_update_service, "list_public_sitemap_updates", entries)
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    locations = [node.text for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert locations == ["https://school.ddup.app/", "https://school.ddup.app/updates", "https://school.ddup.app/updates/7"]
