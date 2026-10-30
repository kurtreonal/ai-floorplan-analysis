from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

DeviceType = Literal['simplex_outlet','duplex_outlet','switch_1gang','switch_2gang','switch_3gang',
                     'switch_3way','data_simplex','data_duplex','cctv','light_single','light_twin',
                     'downlight','troffer','smoke_detector','heat_detector','pull_station','horn_strobe',
                     'pull_horn_strobe','fire_bell','bell_pull','door_chime','push_button','magnetic_contact',
                     'motion_detector','keypad','vibration_detector','panelboard','circuit_breaker',
                     'fire_panel','voice_outlet','utility_box','pull_box','fan_controller']


class AssemblyComponent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material_id: int = Field(gt=0, strict=True)
    quantity: Annotated[Decimal, Field(gt=0, le=1000, max_digits=10, decimal_places=4, allow_inf_nan=False)]


class AssemblyWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0, strict=True)
    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9._-]+$')
    name: str = Field(min_length=1, max_length=255)
    brand: str = Field(min_length=1, max_length=80)
    device_type: DeviceType
    is_default: StrictBool = False
    assumed: StrictBool = False
    scope_complete: StrictBool = True
    specifications: str = Field(default='', max_length=500)
    scope: str = Field(min_length=1, max_length=500)
    source_references: list[Annotated[str,Field(min_length=1,max_length=2048)]] = Field(default_factory=list,max_length=32)
    components: list[AssemblyComponent] = Field(min_length=1, max_length=32)

    @field_validator('name','brand','scope','specifications')
    @classmethod
    def normalized(cls,value):
        if value != value.strip() or '\x00' in value:
            raise ValueError('Use trimmed text without null characters.')
        return value


class AssemblyRead(AssemblyWrite):
    material_id: int
    unit_price: Decimal | None
    currency: str | None
    price_revision_id: int | None
    component_prices: list[dict]
    price_available: bool


class LegendPriceGap(BaseModel):
    legend_id: int
    class_id: int
    name: str
    device_type: DeviceType
    reason: Literal['missing_product', 'missing_component_price', 'default_required', 'incomplete_components']
    compatible_material_ids: list[int]


class AssemblyCatalog(BaseModel):
    writable: bool
    assemblies: list[AssemblyRead]
    name_examples:dict[str,str]=Field(default_factory=dict)
    price_gaps: list[LegendPriceGap] = Field(default_factory=list)
