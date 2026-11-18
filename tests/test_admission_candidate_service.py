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
                    # 与 101 同键（同校同 URL 同类型同新值）的重复检测记录
                    AdmissionChanges(
                        id=104,
                        school_id=1,
                        url="https://example.com/apply",
                        change_type="text_changed",
                        old_value="原摘要",
                        new_value="新摘要",
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
            assert created["school_id"] == 1
            assert created["title"] == "測試學校申请页面文字更新"
            assert set(created["candidate_ids"]) == {101, 104}
            # 同键重复记录 104 一并关联到同一草稿，不再出现在待处理
            review104 = (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == 104))
            ).first()
            assert review104.status == "adopted" and review104.update_id == created["id"]
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
                sources=[{"name": "學校公告", "url": "https://example.com/apply", "support": "新截止日期"}],
                verified_at="2026-11-16T12:00:00+08:00",
            )
            await service.update_content(db, created["id"], content, user_id=1)
            published = await service.publish_update(db, created["id"], user_id=1)
            assert published["status"] == "published"

            # 已发布快讯删除必须填原因；草稿删除免填，原因存 NULL
            with pytest.raises(HTTPException) as missing_reason:
                await service.delete_update(db, created["id"], "", user_id=1)
            assert missing_reason.value.status_code == 422
            deleted = await service.delete_update(db, created["id"], "公开内容下架", user_id=1)
            assert deleted["status"] == "deleted" and deleted["deleted_reason"] == "公开内容下架"
            await service.restore_update(db, created["id"], user_id=1)
            draft_deleted = await service.delete_update(db, created["id"], "", user_id=1)
            assert draft_deleted["status"] == "deleted" and draft_deleted["deleted_reason"] is None
            await service.restore_update(db, created["id"], user_id=1)

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

            # 从未发布的草稿删除后释放候选：候选恢复待处理，可重新生成新草稿
            draft2 = await service.create_update(
                db, AdmissionUpdateCreate(school_id=1, candidate_id=102), user_id=1
            )
            await service.delete_update(db, draft2["id"], "", user_id=1)
            assert (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == 102))
            ).first() is None
            pending = await service.list_candidates(db, status="pending")
            assert 102 in {item["id"] for item in pending["items"]}
            draft3 = await service.create_update(
                db, AdmissionUpdateCreate(school_id=1, candidate_id=102), user_id=1
            )
            assert draft3["id"] != draft2["id"]
            # 已发布过的快讯即使删除也不释放候选关联（前述 created 的 review 仍为 adopted）
            assert (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == 101))
            ).first().status == "adopted"

            # 流水线之后再次重复上报同键变化（105）：待处理直接隐藏，"全部"视图仍可见原始记录
            db.add(
                AdmissionChanges(
                    id=105,
                    school_id=1,
                    url="https://example.com/apply",
                    change_type="text_changed",
                    old_value="原摘要",
                    new_value="新摘要",
                    source="weekly",
                    detected_at=now,
                )
            )
            await db.commit()
            pending = await service.list_candidates(db, status="pending")
            assert {item["id"] for item in pending["items"]} == {103}
            all_candidates = await service.list_candidates(db, status="all")
            assert 105 in {item["id"] for item in all_candidates["items"]}
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(run())
