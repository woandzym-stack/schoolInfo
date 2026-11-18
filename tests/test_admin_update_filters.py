"""管理后台快讯/候选列表筛选：类型、学校、地区、学段（学校类型）。"""
import asyncio
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.admission_changes import AdmissionChanges
from app.models.admission_updates import AdmissionUpdates
from app.models.schools import Schools
from app.services import admission_update_service as service

pytest.importorskip("aiosqlite")


async def _seed(db: AsyncSession) -> None:
    now = datetime.now()
    db.add_all(
        [
            Schools(id=1, name="九龍城中學", stage="secondary", district="九龍城區", created_at=now, updated_at=now),
            Schools(id=2, name="沙田小學", stage="primary", district="沙田區", created_at=now, updated_at=now),
            Schools(id=3, name="無地區中學", stage="secondary", district=None, created_at=now, updated_at=now),
        ]
    )
    db.add_all(
        [
            AdmissionUpdates(
                id=11, school_id=1, change_kind="opened", status="published",
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
            AdmissionUpdates(
                id=12, school_id=2, change_kind="opened", status="draft",
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
            AdmissionUpdates(
                id=13, school_id=1, change_kind="closed", status="published",
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
        ]
    )
    db.add_all(
        [
            AdmissionChanges(
                id=101, school_id=1, url="https://example.com/a", change_type="added",
                source="weekly", detected_at=now,
            ),
            AdmissionChanges(
                id=102, school_id=2, url="https://example.com/b", change_type="added",
                source="weekly", detected_at=now,
            ),
            AdmissionChanges(
                id=103, school_id=1, url="https://example.com/c", change_type="removed",
                source="weekly", detected_at=now,
            ),
        ]
    )
    await db.commit()


async def _with_db(run):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    db = AsyncSession(engine, expire_on_commit=False)
    try:
        await _seed(db)
        await run(db)
    finally:
        await db.close()
        await engine.dispose()


def _ids(result) -> set[int]:
    return {item["id"] for item in result["items"]}


def test_admin_updates_filters():
    async def run(db: AsyncSession):
        assert _ids(await service.list_admin_updates(db)) == {11, 12, 13}
        assert _ids(await service.list_admin_updates(db, change_kind="opened")) == {11, 12}
        assert _ids(await service.list_admin_updates(db, school_id=1)) == {11, 13}
        assert _ids(await service.list_admin_updates(db, district="沙田區")) == {12}
        assert _ids(await service.list_admin_updates(db, stage="secondary")) == {11, 13}
        assert _ids(await service.list_admin_updates(db, change_kind="opened", stage="secondary")) == {11}
        assert _ids(await service.list_admin_updates(db, status="published", district="九龍城區")) == {11, 13}
        empty = await service.list_admin_updates(db, district="不存在地區")
        assert empty["total"] == 0 and empty["items"] == []

    asyncio.run(_with_db(run))


def test_candidates_filters():
    async def run(db: AsyncSession):
        assert _ids(await service.list_candidates(db, status="all")) == {101, 102, 103}
        assert _ids(await service.list_candidates(db, status="all", change_type="added")) == {101, 102}
        assert _ids(await service.list_candidates(db, status="all", school_id=1)) == {101, 103}
        assert _ids(await service.list_candidates(db, status="all", district="沙田區")) == {102}
        assert _ids(await service.list_candidates(db, status="all", stage="primary")) == {102}
        assert _ids(await service.list_candidates(db, status="all", change_type="added", stage="secondary")) == {101}
        # 原有默认待处理筛选不受新参数影响
        assert _ids(await service.list_candidates(db, change_type="added")) == {101, 102}

    asyncio.run(_with_db(run))


def test_admin_updates_exclude_deleted_by_default():
    async def run(db: AsyncSession):
        # u12 为草稿，删除后默认列表不再显示，仅"已删除"筛选可见
        await service.delete_update(db, 12, "", user_id=1)
        assert _ids(await service.list_admin_updates(db)) == {11, 13}
        assert _ids(await service.list_admin_updates(db, status="deleted")) == {12}
        assert _ids(await service.list_admin_updates(db, status="draft")) == set()

    asyncio.run(_with_db(run))


def test_school_districts():
    async def run(db: AsyncSession):
        districts = await service.list_school_districts(db)
        assert districts == sorted(["九龍城區", "沙田區"])

    asyncio.run(_with_db(run))
