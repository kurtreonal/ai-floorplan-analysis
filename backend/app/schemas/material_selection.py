from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field,StrictBool,model_validator
from typing import Literal
from app.services.wiring_material_pairing import PurchasePrice
from app.services.layout_materials import LayoutType,LayoutSelection


class WorkspaceProduct(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind: Literal['device','wire']
    candidate_run_id: str=Field(min_length=1,max_length=160)
    material_id: int=Field(gt=0,strict=True)
    class_id: int | None=Field(default=None,ge=0,strict=True)
    conduit_id: int | None=Field(default=None,gt=0,strict=True)
    conductor_count: int | None=Field(default=None,ge=1,le=1000,strict=True)
    conductor_count_assumed: StrictBool | None=None
    wire_meters_per_unit: float | None=Field(default=None,gt=0,le=100000,allow_inf_nan=False)
    conduit_meters_per_unit: float | None=Field(default=None,gt=0,le=100000,allow_inf_nan=False)

    @model_validator(mode='after')
    def device_class(self):
        if self.kind=='device' and self.class_id is None:raise ValueError('Choose a classified device first.')
        return self


class AutomaticMaterialDefaults(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(ge=0,strict=True)
    conductor_count: int=Field(ge=1,le=1000,strict=True)
    assumed: StrictBool=True
    wire_material_id: int | None=Field(default=None,gt=0,strict=True)
    wire_material_ids: dict[LayoutType,int | None]=Field(default_factory=dict,max_length=3)


class PlanLayoutWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    expected_version: int=Field(ge=0,strict=True)
    layout_type: LayoutSelection


class MaterialSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    wire: str=Field(default='',pattern=r'^(?:[1-9]\d*)?$')
    conduit: str=Field(default='',pattern=r'^(?:[1-9]\d*)?$')
    wireMetersPerUnit: float | None=Field(default=None,gt=0,le=100000,allow_inf_nan=False)
    wirePricePerMeter: float | None=Field(default=None,ge=0,le=1000000000,allow_inf_nan=False)
    purchasePricing: dict[str,PurchasePrice]=Field(default_factory=dict,max_length=2)
    deviceMaterials: dict[str,int]=Field(default_factory=dict,max_length=200)
    assumeConnections: StrictBool | None=None
    layoutType: LayoutSelection | None=None
    conductorCount: int | None=Field(default=None,ge=1,le=1000,strict=True)
    itemMaterials: dict[str,WorkspaceProduct]=Field(default_factory=dict,max_length=5000)
    automaticDefaults: AutomaticMaterialDefaults | None=None


class MaterialSelectionWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    expected_version: int=Field(ge=0,strict=True)
    floor_plan_id: int | None=Field(default=None,gt=0,strict=True)
    settings: MaterialSelection
