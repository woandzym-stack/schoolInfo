from typing import Optional

from pydantic import BaseModel, Field


class LinkReportIn(BaseModel):
    """报告插班链接错误（匿名提交）"""

    school_id: int
    url: str = Field(..., max_length=500)
    link_text: Optional[str] = Field(default=None, max_length=255)
    grades: Optional[str] = Field(default=None, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)
