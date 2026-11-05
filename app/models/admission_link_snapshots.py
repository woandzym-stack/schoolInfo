from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import DateTime, Integer, String
from sqlmodel import SQLModel, Field
from typing import Optional


class AdmissionLinkSnapshots(SQLModel, table=True):
    """申请链接落地页内容指纹基线"""
    __tablename__ = "admission_link_snapshots"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 关联 schools.id
    school_id: int = Field(sa_column=Column("school_id", Integer, nullable=False))
    # 申请链接
    url: str = Field(sa_column=Column("url", String(500), nullable=False))
    # 内容指纹 sha256
    fingerprint: str = Field(sa_column=Column("fingerprint", String(64), nullable=False))
    # text=可见文本哈希 / binary=字节哈希
    content_kind: str = Field(default="text", sa_column=Column("content_kind", String(10), nullable=False))
    # 页面文本前200字摘要（变更报告可读性用）
    text_excerpt: Optional[str] = Field(default=None, sa_column=Column("text_excerpt", String(200)))
    # 最近一次健康检查时间
    fetched_at: datetime = Field(sa_column=Column("fetched_at", DateTime, nullable=False))