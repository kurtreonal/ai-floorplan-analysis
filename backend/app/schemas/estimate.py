from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[int, Field(strict=True, gt=0)]


class ComponentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_id: Annotated[int, Field(strict=True, ge=0)]
    material_id: Identifier
    units_per_symbol: Annotated[Decimal, Field(gt=0, le=1000, decimal_places=4, allow_inf_nan=False)]


class AdditionalMaterial(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material_id: Identifier
    quantity: Annotated[Decimal, Field(gt=0, lt=Decimal('1e12'), decimal_places=4, allow_inf_nan=False)]


class EstimateWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    route_version_id: Identifier
    components: Annotated[list[ComponentBinding], Field(max_length=1000)]
    conduit_material_id: Identifier
    wire_material_id: Identifier
    conductor_count: Annotated[int, Field(strict=True, ge=1, le=1000)]
    mappings_confirmed: Literal[True]
    additional_materials: Annotated[list[AdditionalMaterial], Field(max_length=200)] = []
    wire_meters_per_unit: Annotated[Decimal | None, Field(gt=0, le=100000, decimal_places=4, allow_inf_nan=False)] = None
    conduit_meters_per_unit: Annotated[Decimal | None, Field(gt=0, le=100000, decimal_places=4, allow_inf_nan=False)] = None
    price_source: Literal['catalog', 'project'] = 'catalog'
    project_price_version_id: Identifier | None = None

    @model_validator(mode="after")
    def unique_classes(self):
        if (self.price_source == 'project') != (self.project_price_version_id is not None):
            raise ValueError('Explicitly select one project price version, or the shared catalog.')
        if len({item.class_id for item in self.components}) != len(self.components):
            raise ValueError("Each class requires exactly one material mapping.")
        if len({item.material_id for item in self.additional_materials}) != len(self.additional_materials):
            raise ValueError('Each additional material requires one quantity.')
        return self


class EstimateItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    line_number: int
    material_id: int
    material_code: str
    material_name: str
    quantity: Decimal
    unit: str
    captured_unit_price: Decimal
    line_total: Decimal


class EstimateResponse(BaseModel):
    id: int
    project_id: int
    version_number: int
    created_by_user_id: int
    created_at: datetime
    currency: str
    total: Decimal
    items: list[EstimateItemResponse]
    source: dict | None


class EstimateOptions(BaseModel):
    route_version_id: int | None
    stale: bool
    route_blocker: str | None = None
    floors: list[int]
    components: list[dict]
    materials: list[dict]
    price_source: str = 'catalog'
    project_price_version_id: int | None = None
