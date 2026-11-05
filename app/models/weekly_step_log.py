from datetime import date, datetime
from sqlalchemy import Column
from sqlalchemy import Date, DateTime, Integer, String
from sqlmodel import SQLModel, Field
from typing import Optional


class WeeklyStepLog(SQLModel, table=True):
    """每周刷新步骤级日志（断点续跑依据）"""
    __tablename__ = "weekly_step_log"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 运行日期
    run_date: date = Field(sa_column=Column("run_date", Date, nullable=False))
    # step1_schools/step2_links/step3_noise/step4_health
    step: str = Field(sa_column=Column("step", String(30), nullable=False))
    # running/success/partial/stale(下游需重跑)/failed/interrupted(进程被kill)
    status: str = Field(default="running", sa_column=Column("status", String(20), nullable=False))
    # 开始时间
    started_at: Optional[datetime] = Field(default=None, sa_column=Column("started_at", DateTime))
    # 结束时间
    finished_at: Optional[datetime] = Field(default=None, sa_column=Column("finished_at", DateTime))
    # 该步统计（JSON），断点续跑跳过此步时从这里取数
    stats: Optional[str] = Field(default=None, sa_column=Column("stats", String(1000)))
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, nullable=False))