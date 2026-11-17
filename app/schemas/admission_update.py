from datetime import date, datetime
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
    scope_text: str = Field(default="", max_length=500)
    change_detail: str = Field(default="", max_length=3000)
    action_text: str = Field(default="", max_length=1500)
    sources: list[AdmissionSourceIn] = Field(default_factory=list, max_length=5)
    official_published_on: Optional[date] = None
    verified_at: Optional[datetime] = None
    correction_note: str = Field(default="", max_length=1000)

    @field_validator("title", "summary", "scope_text", "change_detail", "action_text", "correction_note")
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
            (self.scope_text, "适用范围"),
            (self.change_detail, "变化说明"),
            (self.action_text, "家长下一步"),
        )
        errors.extend(f"{label}不能为空" for value, label in required if not value)
        if not self.sources:
            errors.append("至少需要一个官方来源")
        if any(not source.name or not source.support for source in self.sources):
            errors.append("每个官方来源都需要填写来源名称和对应信息")
        if self.verified_at is None:
            errors.append("本站核实时间不能为空")
        return errors


class AdmissionUpdateCreate(AdmissionUpdateContent):
    school_id: int
    candidate_id: Optional[int] = None


class AdmissionUpdateDelete(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("删除原因不能为空")
        return value
