from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[int, Field(strict=True, gt=0)]
Column = Annotated[str, Field(pattern=r'^[A-Z]{1,2}$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Columns(StrictModel):
    name: Column
    unit: Column
    unit_price: Column
    code: Column | None = None
    specification: Column | None = None
    currency: Column | None = None
    quantity: Column | None = None

    @model_validator(mode='after')
    def distinct(self):
        values = [value for value in self.model_dump().values() if value is not None]
        if len(set(values)) != len(values):
            raise ValueError('Map each field to a different source column.')
        return self


class ImportMapping(StrictModel):
    kind: Literal['price_list', 'client_bom']
    sheet: str = Field(min_length=1, max_length=100)
    header_row: int = Field(default=1, ge=1, le=10000, strict=True)
    columns: Columns
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')

    @model_validator(mode='after')
    def required_fields(self):
        if not self.columns.currency and not self.currency:
            raise ValueError('Map currency or explicitly specify it.')
        if self.kind == 'client_bom' and not self.columns.quantity:
            raise ValueError('Map the client quantity for a client BOM.')
        if self.kind == 'price_list' and self.columns.quantity:
            raise ValueError('Use Client BOM to retain source quantities.')
        return self


class RowChoice(StrictModel):
    row_id: str = Field(min_length=1, max_length=120)
    material_id: Identifier | None = None
    units_per_purchase: Annotated[Decimal | None, Field(gt=0, le=100000, decimal_places=4, allow_inf_nan=False)] = None
    excluded: bool = False


class PreviewRequest(StrictModel):
    mapping: ImportMapping
    choices: list[RowChoice] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def unique_rows(self):
        if len({row.row_id for row in self.choices}) != len(self.choices):
            raise ValueError('Duplicate row decisions.')
        return self


class ApplyRequest(PreviewRequest):
    request_id: UUID
    file_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    preview_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_version: int = Field(ge=0, strict=True)
    confirmed: Literal[True]


class VersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    version_number: int
    kind: str
    filename: str
    file_sha256: str
    created_by_user_id: int
    created_at: datetime


class VersionDetail(VersionSummary):
    document: dict
    comparison: list[dict] | None = None


class ImportInspection(BaseModel):
    file_sha256: str
    sheets: list[str]
    sheet: str
    header_row: int
    columns: list[dict[str, str]]
    sample: list[dict]


class ProjectImportPreview(BaseModel):
    file_sha256: str
    preview_token: str
    expected_version: int
    document: dict
    ready: bool
    materials: list[dict]
