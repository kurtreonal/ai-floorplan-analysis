from typing import Annotated, Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator


DatabaseId = Annotated[int, Field(gt=0, le=9_223_372_036_854_775_807)]
ModelClassId = Annotated[StrictInt, Field(ge=0, le=2_147_483_647)]
SymbolLegendName = Annotated[str, Field(min_length=1, max_length=255)]


class SymbolLegendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: DatabaseId
    class_id: ModelClassId
    name: SymbolLegendName


class SymbolLegendWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: ModelClassId
    name: SymbolLegendName
    is_active: StrictBool

    @field_validator("name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise ValueError("Symbol legend names must be normalized.")
        return value


class SymbolLegendAdminResponse(SymbolLegendResponse):
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LegendReferenceArtworkWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference_id: str = Field(min_length=1, max_length=64, pattern=r'^R[0-9_]+-(as_shown|wall|ceiling)$')
    legend_ids: list[DatabaseId] | None = Field(default=None, min_length=1, max_length=256)


class LegendAvailabilityWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    legend_ids: list[DatabaseId] = Field(min_length=1, max_length=256)
    is_active: StrictBool


class LegendReferenceImageResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    label: str
    reference: str
    variant: Literal['as_shown', 'wall', 'ceiling']
    source: Literal['Supplied PEC reference']
