import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.admission_change_reviews import AdmissionChangeReviews
from app.models.admission_changes import AdmissionChanges
from app.models.schools import Schools
from app.schemas.admission_update import AdmissionUpdateContent, AdmissionUpdateCreate
from app.services import admission_update_service as service

pytest.importorskip("aiosqlite")


def test_candidate_draft_lifecycle_and_source_table_immutability():
    async def run():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        db = AsyncSession(engine, expire_on_commit=False)
        try:
            now = datetime.now()
            db.add(
                Schools(
                    id=1,
                    name="測試學校",
                    simple_name="测试学校",
                    stage="secondary",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.add_all(
                [
                    AdmissionChanges(
                        id=101,
                        school_id=1,
                        url="https://example.com/apply",
                        change_type="text_changed",
                        old_value="原摘要",
                        new_value="新摘要",
                        source="weekly",
                        detected_at=now,
                    ),
                    AdmissionChanges(
                        id=102,
                        school_id=1,
                        url="https://example.com/other",
                        change_type="removed",
                        old_value="原入口",
                        new_value=None,
                        source="weekly",
                        detected_at=now,
                    ),
                    AdmissionChanges(
                        id=103,
                        school_id=1,
                        url="javascript:alert(1)",
                        change_type="added",
                        old_value=None,
                        new_value="不安全入口",
                        source="weekly",
                        detected_at=now,
                    ),
                ]
            )
            await db.commit()

            created = await service.create_update(
                db,
                AdmissionUpdateCreate(school_id=1, candidate_id=101),
                user_id=1,
            )
            assert created["status"] == "draft"
            assert created["candidate_ids"] == [101]
            assert created["sources"] == [{"name": "学校申请页面", "url": "https://example.com/apply", "support": ""}]
            with pytest.raises(HTTPException) as incomplete:
                await service.publish_update(db, created["id"], user_id=1)
            assert incomplete.value.status_code == 422

            repeated = await service.create_update(
                db,
                AdmissionUpdateCreate(school_id=1, candidate_id=101),
                user_id=1,
            )
            assert repeated["id"] == created["id"]
            with pytest.raises(HTTPException) as adopted_ignore:
                await service.ignore_candidate(db, 101, user_id=1)
            assert adopted_ignore.value.status_code == 409
            with pytest.raises(HTTPException) as adopted_restore:
                await service.restore_candidate(db, 101)
            assert adopted_restore.value.status_code == 409

            await service.ignore_candidate(db, 102, user_id=1)
            with pytest.raises(HTTPException) as ignored_create:
                await service.create_update(
                    db,
                    AdmissionUpdateCreate(school_id=1, candidate_id=102),
                    user_id=1,
                )
            assert ignored_create.value.status_code == 409
            await service.restore_candidate(db, 102)

            with pytest.raises(HTTPException) as unsafe_url:
                await service.create_update(
                    db,
                    AdmissionUpdateCreate(school_id=1, candidate_id=103),
                    user_id=1,
                )
            assert unsafe_url.value.status_code == 422

            content = AdmissionUpdateContent(
                title="測試快訊",
                summary="測試摘要",
                scope_text="中二",
                change_detail="人工核實後的變化",
                action_text="人工核實後的行動",
                sources=[{"name": "學校公告", "url": "https://example.com/apply", "support": "新截止日期"}],
                verified_at="2026-11-16T12:00:00+08:00",
            )
            await service.update_content(db, created["id"], content, user_id=1)
            published = await service.publish_update(db, created["id"], user_id=1)
            assert published["status"] == "published"

            review = (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == 101))
            ).first()
            assert review.status == "adopted"
            original = (await db.exec(select(AdmissionChanges).where(AdmissionChanges.id == 101))).first()
            assert original.old_value == "原摘要"
            assert original.new_value == "新摘要"
            assert original.url == "https://example.com/apply"
            candidates = await service.list_candidates(db, status="pending")
            assert candidates["total"] == 2
            assert {item["id"] for item in candidates["items"]} == {102, 103}
            assert next(item for item in candidates["items"] if item["id"] == 103)["url"] is None

            original_commit = db.commit

            async def failing_commit():
                raise RuntimeError("simulated commit failure")

            db.commit = failing_commit
            with pytest.raises(RuntimeError, match="simulated commit failure"):
                await service.create_update(
                    db,
                    AdmissionUpdateCreate(school_id=1, candidate_id=102),
                    user_id=1,
                )
            db.commit = original_commit
            assert (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == 102))
            ).first() is None
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(run())
