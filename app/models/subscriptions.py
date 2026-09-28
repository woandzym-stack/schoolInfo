from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, SQLModel


class Subscriptions(SQLModel, table=True):
    """订阅表：一行 = 一个用户 + 一所学校 + 一个年级（all 表示订阅该校全部年级）"""
    __tablename__ = "subscriptions"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 关联 users.id
    user_id: int = Field(sa_column=Column("user_id", Integer, nullable=False))
    # 关联 schools.id
    school_id: int = Field(sa_column=Column("school_id", Integer, nullable=False))
    # P1-P6 / S1-S6 / all
    grade: str = Field(sa_column=Column("grade", String(10), nullable=False))
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, nullable=False))
