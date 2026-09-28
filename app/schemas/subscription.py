from typing import List, Optional

from pydantic import BaseModel, Field


class SubscribeIn(BaseModel):
    """订阅请求：grades 空数组表示订阅该校全部年级（存 all）。"""
    school_id: int
    grades: List[str] = Field(default_factory=list, max_length=6)


class SchoolSubscriptionOut(BaseModel):
    """按学校聚合的订阅视图（我的订阅列表 / 订阅操作后的最终状态）。"""
    school_id: int
    name: str
    stage: str
    district: Optional[str] = None
    grades: List[str]
    subscribed_at: str


class AdmissionLinkOut(BaseModel):
    url: str
    link_text: Optional[str] = None
    grades: str
