from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

ChangeKind = Literal[
    "announcement",
    "opened",
    "deadline_changed",
    "requirements_changed",
    "grades_changed",
    "assessment_changed",
    "closed",
    "entry_updated",
    "other",
]


class AdmissionSourceIn(BaseModel):
    name: str = Field(default="", max_length=200)
    url: HttpUrl
    support: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def reject_credentials(self) -> "AdmissionSourceIn":
        if self.url.username or self.url.password:
            raise ValueError("来源 URL 不得包含用户名或密码")
        return self


class AdmissionUpdateContent(BaseModel):
    change_kind: ChangeKind = "other"
    title: str = Field(default="", max_length=120)
    summary: str = Field(default="", max_length=300)
    sources: list[AdmissionSourceIn] = Field(default_factory=list, max_length=5)
    verified_at: Optional[datetime] = None

    @field_validator("title", "summary")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("sources")
    @classmethod
    def strip_source_text(cls, sources: list[AdmissionSourceIn]) -> list[AdmissionSourceIn]:
        for source in sources:
            source.name = source.name.strip()
            source.support = source.support.strip()
        return sources

    def sources_for_storage(self) -> list[dict[str, str]]:
        return [source.model_dump(mode="json") for source in self.sources]

    def publish_errors(self) -> list[str]:
        errors: list[str] = []
        required = (
            (self.title, "标题"),
            (self.summary, "一句话重点"),
        )
        errors.extend(f"{label}不能为空" for value, label in required if not value)
        if not self.sources:
            errors.append("至少需要一个官方来源")
        if any(not source.name for source in self.sources):
            errors.append("每个官方来源都需要填写来源名称")
        if self.verified_at is None:
            errors.append("本站核实时间不能为空")
        return errors


class AdmissionUpdateCreate(AdmissionUpdateContent):
    school_id: int
    candidate_id: Optional[int] = None


class AdmissionUpdateDelete(BaseModel):
    # 草稿删除可为空；已发布快讯删除必填，由 Service 按当前状态校验
    reason: str = Field(default="", max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        return value.strip()
