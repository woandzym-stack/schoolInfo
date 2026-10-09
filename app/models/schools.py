from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, SQLModel


class Schools(SQLModel, table=True):
    """香港学校信息表"""

    __tablename__ = "schools"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 学校名称（繁体）
    name: str = Field(sa_column=Column("name", String(255), nullable=False))
    # 学校名称的简体版本，用于简体关键字搜索（与 name 双列匹配，查询时不做简繁转换）
    simple_name: Optional[str] = Field(default=None, sa_column=Column("simple_name", String(255)))
    # 学校网址
    url: Optional[str] = Field(default=None, sa_column=Column("url", String(500)))
    # schooland.hk 详情页链接
    detail_url: Optional[str] = Field(default=None, sa_column=Column("detail_url", String(500)))
    # 学校类型
    type: Optional[str] = Field(default=None, sa_column=Column("type", String(50)))
    # 地区
    district: Optional[str] = Field(default=None, sa_column=Column("district", String(50)))
    # 学校组别
    banding: Optional[str] = Field(default=None, sa_column=Column("banding", String(20)))
    # 教学语言
    language: Optional[str] = Field(default=None, sa_column=Column("language", String(50)))
    # 性别
    gender: Optional[str] = Field(default=None, sa_column=Column("gender", String(20)))
    # 宗教
    religion: Optional[str] = Field(default=None, sa_column=Column("religion", String(100)))
    # 学段：primary=小学, secondary=中学
    stage: str = Field(default="secondary", sa_column=Column("stage", String(10), nullable=False))
    # 小学校网编号（仅小学有值）
    school_net: Optional[str] = Field(default=None, sa_column=Column("school_net", String(20)))
    # 地址
    address: Optional[str] = Field(default=None, sa_column=Column("address", String(500)))
    # 电话
    phone: Optional[str] = Field(default=None, sa_column=Column("phone", String(50)))
    # 电邮
    email: Optional[str] = Field(default=None, sa_column=Column("email", String(255)))
    # 大考網站链接（bigexam.hk 学校页，一般仅中学有）
    bigexam_url: Optional[str] = Field(default=None, sa_column=Column("bigexam_url", String(500)))
    # 全港排名下限（bigexam hkRank 区间）
    hk_rank_low: Optional[int] = Field(default=None, sa_column=Column("hk_rank_low", Integer))
    # 全港排名上限（bigexam hkRank 区间）
    hk_rank_high: Optional[int] = Field(default=None, sa_column=Column("hk_rank_high", Integer))
    # 全港参与排名学校总数
    hk_rank_ttl: Optional[int] = Field(default=None, sa_column=Column("hk_rank_ttl", Integer))
    # 全港排名抓取时间
    rank_updated_at: Optional[datetime] = Field(default=None, sa_column=Column("rank_updated_at", DateTime))
    # 申请链接
    admission_link: Optional[str] = Field(default=None, sa_column=Column("admission_link", String(500)))
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, nullable=False))
    updated_at: datetime = Field(sa_column=Column("updated_at", DateTime, nullable=False))
