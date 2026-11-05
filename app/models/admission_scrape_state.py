from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import DateTime, Integer, String
from sqlmodel import SQLModel, Field
from typing import Optional


class AdmissionScrapeState(SQLModel, table=True):
    """学校申请链接抓取基线状态"""
    __tablename__ = "admission_scrape_state"

    # 关联 schools.id
    school_id: int = Field(sa_column=Column("school_id", Integer, primary_key=True))
    # nonempty=上次观测非空 / empty=上次观测为空集
    last_result: str = Field(sa_column=Column("last_result", String(10), nullable=False))
    # 最近一次成功观测时间；成功时显式更新，失败不更新
    scraped_at: datetime = Field(sa_column=Column("scraped_at", DateTime, nullable=False))