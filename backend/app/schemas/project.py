from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProjectStatus = Literal[
    "draft",
    "uploaded",
    "processing",
    "needs_review",
    "layout_ready",
    "routing_ready",
    "estimated",
    "report_ready",
    "archived",
]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=500)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    status: ProjectStatus
    client_name: str | None
    location: str | None
    created_at: datetime
    updated_at: datetime
