from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, SQLModel


class AdmissionChangeReviews(SQLModel, table=True):
    """外部申请变化的轻量处置；无记录表示待处理。"""

    __tablename__ = "admission_change_reviews"

    change_id: int = Field(sa_column=Column("change_id", Integer, primary_key=True))
    # adopted/ignored；adopted 必须关联快讯，ignored 不得关联
    status: str = Field(sa_column=Column("status", String(20), nullable=False, index=True))
    update_id: Optional[int] = Field(default=None, sa_column=Column("update_id", Integer, index=True))
    reviewed_by: int = Field(sa_column=Column("reviewed_by", Integer, nullable=False))
    reviewed_at: datetime = Field(sa_column=Column("reviewed_at", DateTime, nullable=False))
