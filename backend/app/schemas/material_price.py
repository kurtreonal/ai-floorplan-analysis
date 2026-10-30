from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated,Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MaterialPriceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=4, allow_inf_nan=False)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def explicit_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("An explicit timezone is required.")
        return value.astimezone(timezone.utc)


class CatalogPriceWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=0,strict=True)
    unit_price:Annotated[Decimal,Field(ge=0,max_digits=16,decimal_places=4,allow_inf_nan=False)]
    currency:Literal['PHP','USD']='PHP'


class CatalogMaterial(BaseModel):
    id:int
    code:str
    name:str
    unit:str
    category:str
    is_active:bool
    unit_price:Decimal|None
    currency:str|None
    revision:int
    is_assembly:bool=False


class CatalogMaterialCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    code:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9._/-]+$')
    name:str=Field(min_length=1,max_length=220)
    category:str=Field(min_length=1,max_length=100)
    unit:Literal['piece','unit','set','meter','length','roll']
    unit_price:Annotated[Decimal,Field(ge=0,max_digits=16,decimal_places=4,allow_inf_nan=False)]
    currency:Literal['PHP','USD']='PHP'
    meters_per_unit:float|None=Field(default=None,gt=0,le=100000,allow_inf_nan=False)

    @field_validator('name','category')
    @classmethod
    def plain_catalog_text(cls,value):
        if any(ord(character)<32 for character in value):raise ValueError('Use plain text without control characters.')
        return value
