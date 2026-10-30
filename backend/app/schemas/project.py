from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator
from app.services.layout_materials import LayoutType


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


ServiceType = Literal['new_construction', 'renovation', 'electrical_installation', 'maintenance_repair', 'data_installation', 'cctv_installation', 'other']
BlueprintAvailability = Literal['available_now', 'later', 'unavailable']
PROJECT_DETAIL_FIELDS = ('name', 'client_name', 'location', 'contact_number', 'service_type', 'service_types', 'layout_type',
                         'service_type_other', 'preferred_start_date', 'blueprint_availability','allocated_budget')


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=500)
    contact_number: str | None = Field(default=None, max_length=64)
    service_type: ServiceType | None = None
    service_types: list[ServiceType] = Field(default_factory=list, max_length=7)
    layout_type: LayoutType | None = None
    service_type_other: str | None = Field(default=None, max_length=255)
    preferred_start_date: date | None = Field(default=None, ge=date(1000, 1, 1))
    blueprint_availability: BlueprintAvailability | None = None
    allocated_budget: Decimal | None=Field(default=None,ge=0,max_digits=14,decimal_places=2)

    @field_validator('contact_number')
    @classmethod
    def meaningful_phone(cls,value):
        if value is not None and sum(c.isdigit() for c in value)<7:
            raise ValueError('Enter at least seven phone-number digits.')
        return value

    @field_validator('preferred_start_date', mode='before')
    @classmethod
    def date_only(cls, value):
        if value is not None and type(value) is not date and (
            not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)
        ):
            raise ValueError('Use a date in YYYY-MM-DD format.')
        return value


class ProjectCreate(ProjectMetadata):
    allocated_budget: Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    name: str = Field(min_length=1, max_length=255)
    client_id: int | None = Field(default=None, gt=0)
    designer_id: int | None = Field(default=None, gt=0)
    location: str = Field(min_length=1, max_length=500)
    contact_number: str = Field(min_length=7, max_length=64, pattern=r'^[+0-9() .\-]+$')

    @model_validator(mode='after')
    def other_service_description(self):
        if (self.service_type == 'other' or 'other' in self.service_types) and not self.service_type_other:
            raise ValueError('Describe the Other project/service type.')
        if self.service_type != 'other' and 'other' not in self.service_types and self.service_type_other:
            raise ValueError('Other description requires the Other project/service type.')
        return self


class ProjectDetailsValidation(ProjectCreate):
    allocated_budget: Decimal | None=Field(default=None,ge=0,max_digits=14,decimal_places=2)


class ProjectUpdate(ProjectMetadata):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    expected_details_revision: str = Field(pattern=r'^[a-f0-9]{64}$')

    @field_validator('allocated_budget')
    @classmethod
    def budget_cannot_be_cleared(cls,value):
        if value is None:raise ValueError('Enter an allocated budget.')
        return value

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
    client_id: int | None = None
    designer_name: str | None = None
    name: str
    status: ProjectStatus
    client_name: str | None
    location: str | None
    contact_number: str | None
    service_type: ServiceType | None
    service_types: list[ServiceType] = Field(default_factory=list)
    layout_type: LayoutType | None = None
    allocated_budget: Decimal | None=None
    intake_status: str = 'assigned'
    preferred_designer_id: int | None = None
    preferred_designer_name: str | None = None
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
