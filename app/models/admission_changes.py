from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import DateTime, Integer, String
from sqlmodel import SQLModel, Field
from typing import Optional


class AdmissionChanges(SQLModel, table=True):
    """申请链接变更记录"""
    __tablename__ = "admission_changes"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 关联 schools.id
    school_id: int = Field(sa_column=Column("school_id", Integer, nullable=False))
    # 变更涉及的链接
    url: str = Field(sa_column=Column("url", String(500), nullable=False))
    # added/removed/text_changed/grades_changed/content_changed
    change_type: str = Field(sa_column=Column("change_type", String(20), nullable=False))
    # 旧值：文字/年级为原值，内容变化为旧页面前200字摘要
    old_value: Optional[str] = Field(default=None, sa_column=Column("old_value", String(500)))
    # 新值：同上，为新页面前200字摘要
    new_value: Optional[str] = Field(default=None, sa_column=Column("new_value", String(500)))
    # weekly=流水线 / manual=手动重抓
    source: str = Field(default="manual", sa_column=Column("source", String(20), nullable=False))
    # 检测时间（会话时区东八区）
    detected_at: datetime = Field(sa_column=Column("detected_at", DateTime, nullable=False))