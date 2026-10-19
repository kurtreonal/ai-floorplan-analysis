from datetime import date, datetime
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


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


ServiceType = Literal['new_construction', 'renovation', 'electrical_installation', 'maintenance_repair', 'other']
BlueprintAvailability = Literal['available_now', 'later', 'unavailable']
PROJECT_DETAIL_FIELDS = ('name', 'client_name', 'location', 'contact_number', 'service_type',
                         'service_type_other', 'preferred_start_date', 'blueprint_availability')


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=500)
    contact_number: str | None = Field(default=None, max_length=64)
    service_type: ServiceType | None = None
    service_type_other: str | None = Field(default=None, max_length=255)
    preferred_start_date: date | None = Field(default=None, ge=date(1000, 1, 1))
    blueprint_availability: BlueprintAvailability | None = None

    @field_validator('preferred_start_date', mode='before')
    @classmethod
    def date_only(cls, value):
        if value is not None and type(value) is not date and (
            not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)
        ):
            raise ValueError('Use a date in YYYY-MM-DD format.')
        return value


class ProjectCreate(ProjectMetadata):
    name: str = Field(min_length=1, max_length=255)

    @model_validator(mode='after')
    def other_service_description(self):
        if self.service_type == 'other' and not self.service_type_other:
            raise ValueError('Describe the Other project/service type.')
        if self.service_type != 'other' and self.service_type_other:
            raise ValueError('Other description requires the Other project/service type.')
        return self


class ProjectUpdate(ProjectMetadata):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    expected_details_revision: str = Field(pattern=r'^[a-f0-9]{64}$')

    @field_validator('name', mode='before')
    @classmethod
    def name_cannot_be_cleared(cls, value):
        if value is None:
            raise ValueError('Project name is required.')
        return value


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    status: ProjectStatus
    client_name: str | None
    location: str | None
    contact_number: str | None
    service_type: ServiceType | None
    service_type_other: str | None
    preferred_start_date: date | None
    blueprint_availability: BlueprintAvailability | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def details_revision(self) -> str:
        # Content-based concurrency works even when MySQL timestamps have second precision.
        values = {key: getattr(self, key) for key in PROJECT_DETAIL_FIELDS}
        return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()
