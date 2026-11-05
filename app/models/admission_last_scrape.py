from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import DateTime, Integer, String
from sqlmodel import SQLModel, Field
from typing import Optional


class AdmissionLastScrape(SQLModel, table=True):
    """上次抓取原始集合（变更 diff 基准）"""
    __tablename__ = "admission_last_scrape"

    # 关联 schools.id
    school_id: int = Field(sa_column=Column("school_id", Integer, primary_key=True))
    # 抓取到的申请链接（含之后会被清理的）
    url: str = Field(sa_column=Column("url", String(500), primary_key=True))
    # 抓取时解析的适用年级
    grades: Optional[str] = Field(default=None, sa_column=Column("grades", String(100)))
    # 抓取时的锚点文字
    link_text: Optional[str] = Field(default=None, sa_column=Column("link_text", String(255)))
    # 最近一次抓到此链接的时间
    scraped_at: datetime = Field(sa_column=Column("scraped_at", DateTime, nullable=False))