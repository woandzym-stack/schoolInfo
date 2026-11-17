from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, Text
from sqlmodel import Field, SQLModel


class AdmissionUpdates(SQLModel, table=True):
    """人工编辑的申请快讯；每条记录只保存一份当前内容。"""

    __tablename__ = "admission_updates"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    school_id: int = Field(sa_column=Column("school_id", Integer, nullable=False, index=True))
    # announcement/opened/deadline_changed/requirements_changed/grades_changed/
    # assessment_changed/closed/entry_updated/other
    change_kind: str = Field(default="other", sa_column=Column("change_kind", String(30), nullable=False))
    title: str = Field(default="", sa_column=Column("title", String(120), nullable=False))
    summary: str = Field(default="", sa_column=Column("summary", String(300), nullable=False))
    scope_text: str = Field(default="", sa_column=Column("scope_text", String(500), nullable=False))
    change_detail: str = Field(default="", sa_column=Column("change_detail", Text, nullable=False))
    action_text: str = Field(default="", sa_column=Column("action_text", Text, nullable=False))
    # [{name, url, support}]，只允许 HTTP(S) 官方来源
    sources_json: List[Dict[str, Any]] = Field(
        default_factory=list, sa_column=Column("sources_json", JSON, nullable=False)
    )
    official_published_on: Optional[date] = Field(default=None, sa_column=Column("official_published_on", Date))
    verified_at: Optional[datetime] = Field(default=None, sa_column=Column("verified_at", DateTime))
    correction_note: str = Field(default="", sa_column=Column("correction_note", Text, nullable=False))
    # draft/published/deleted；deleted 为软删除
    status: str = Field(default="draft", sa_column=Column("status", String(20), nullable=False, index=True))
    deleted_reason: Optional[str] = Field(default=None, sa_column=Column("deleted_reason", String(500)))
    first_published_at: Optional[datetime] = Field(
        default=None, sa_column=Column("first_published_at", DateTime, index=True)
    )
    content_modified_at: Optional[datetime] = Field(default=None, sa_column=Column("content_modified_at", DateTime))
    created_by: int = Field(sa_column=Column("created_by", Integer, nullable=False))
    updated_by: int = Field(sa_column=Column("updated_by", Integer, nullable=False))
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, nullable=False))
    updated_at: datetime = Field(sa_column=Column("updated_at", DateTime, nullable=False))
