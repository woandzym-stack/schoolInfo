"""公开快讯列表：学校维度筛选（与名录一致）与筛选选项生成。"""
import asyncio
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.admission_updates import AdmissionUpdates
from app.models.schools import Schools
from app.services import admission_update_service as service

pytest.importorskip("aiosqlite")


async def _seed(db: AsyncSession) -> None:
    now = datetime.now()
    db.add_all(
        [
            Schools(
                id=1, name="中學A", stage="secondary", district="九龍城區", type="資助", gender="男女",
                banding="1A", language="英文", religion="基督教", created_at=now, updated_at=now,
            ),
            Schools(
                id=2, name="中學B", stage="secondary", district="深水埗區", type="直資", gender="男",
                banding="2B", language="中文", created_at=now, updated_at=now,
            ),
            Schools(
                id=3, name="小學C", stage="primary", district="沙田區", type="資助", gender="男女",
                school_net="91", created_at=now, updated_at=now,
            ),
            Schools(
                id=4, name="小學D", stage="primary", district="沙田區", school_net="0",
                created_at=now, updated_at=now,
            ),
        ]
    )
    db.add_all(
        [
            AdmissionUpdates(
                id=11, school_id=1, change_kind="opened", status="published", first_published_at=now,
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
            AdmissionUpdates(
                id=12, school_id=2, change_kind="closed", status="published", first_published_at=now,
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
            AdmissionUpdates(
                id=13, school_id=3, change_kind="opened", status="published", first_published_at=now,
                created_by=1, updated_by=1, created_at=now, updated_at=now,
            ),
            AdmissionUpdates(
                id=14, school_id=1, change_kind="other", status="draft",
                created_by=1, updated_by=1, created_at=now, updated_at=now,
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


def test_public_updates_school_filters():
    async def run(db: AsyncSession):
        # 草稿不可见；change_kind 参数保留供公开 API 使用
        assert _ids(await service.list_public_updates(db)) == {11, 12, 13}
        assert _ids(await service.list_public_updates(db, change_kind="opened")) == {11, 13}
        assert _ids(await service.list_public_updates(db, stage="secondary")) == {11, 12}
        assert _ids(await service.list_public_updates(db, stage="primary")) == {13}
        assert _ids(await service.list_public_updates(db, district="九龍城區")) == {11}
        assert _ids(await service.list_public_updates(db, school_type="直資")) == {12}
        assert _ids(await service.list_public_updates(db, gender="男")) == {12}
        assert _ids(await service.list_public_updates(db, language="英文")) == {11}
        assert _ids(await service.list_public_updates(db, religion="基督教")) == {11}
        assert _ids(await service.list_public_updates(db, school_net="91")) == {13}
        # 组别与名录一致按前缀匹配：整档 '1' 覆盖 1A，细分 '1A' 精确到档内
        assert _ids(await service.list_public_updates(db, banding="1")) == {11}
        assert _ids(await service.list_public_updates(db, banding="1A")) == {11}
        assert _ids(await service.list_public_updates(db, banding="2")) == {12}
        # 组合筛选：学段 + 地区 + 类型
        combined = await service.list_public_updates(db, stage="secondary", district="深水埗區", school_type="直資")
        assert _ids(combined) == {12}

    asyncio.run(_with_db(run))


def test_public_filter_options_by_stage():
    async def run(db: AsyncSession):
        defs_all, _ = await service.list_public_filter_options(db, "")
        assert [d["key"] for d in defs_all] == ["district", "type", "gender", "religion"]

        defs_sec, opts_sec = await service.list_public_filter_options(db, "secondary")
        assert [d["key"] for d in defs_sec] == ["district", "banding", "type", "gender", "language", "religion"]
        assert opts_sec["district"] == sorted(["九龍城區", "深水埗區"])
        assert opts_sec["banding"] == ["1", "1A", "2", "2B"]
        assert opts_sec["language"] == sorted(["英文", "中文"])

        defs_pri, opts_pri = await service.list_public_filter_options(db, "primary")
        assert [d["key"] for d in defs_pri] == ["district", "type", "gender", "school_net", "religion"]
        # 校网排除 '0'（直资/私立不参与派位校网），按编号数值排序
        assert opts_pri["school_net"] == ["91"]
        assert opts_pri["district"] == ["沙田區"]

    asyncio.run(_with_db(run))
