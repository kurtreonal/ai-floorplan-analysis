from typing import Annotated,Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,StrictFloat,StrictInt

Length=Annotated[StrictFloat|StrictInt,Field(gt=0,le=1000,allow_inf_nan=False)]
Elevation=Annotated[StrictFloat|StrictInt,Field(ge=-10000,le=10000,allow_inf_nan=False)]


class PlanMeasurementInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    # Null means retain reliable source metadata; otherwise use the displayed
    # input defaults. Neither paper dimensions nor the nominal ratio calibrate.
    paper_size:Literal['A4','A3','A2','A1','A0']|None=None
    orientation:Literal['portrait','landscape']|None=None
    scale_denominator:Annotated[StrictFloat|StrictInt,Field(ge=1,le=100000,allow_inf_nan=False)]=100
    floor_elevation_meters:Elevation|None=None
    floor_to_ceiling_height_meters:Length|None=None
    service_elevation_meters:Elevation|None=None
    outlet_center_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]=.3
    switch_center_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]=1.2


class PlanMeasurementWrite(PlanMeasurementInput):
    expected_revision:Annotated[StrictInt,Field(ge=0)]
    request_id:UUID


class PlanMeasurementResponse(BaseModel):
    floor_plan_id:Annotated[int,Field(gt=0)]
    revision:Annotated[int,Field(ge=0)]
    floor_elevation_meters:float|None=None
    settings:PlanMeasurementInput
    pages:list[dict]=Field(default_factory=list,max_length=10000)
    source_pages:list[dict]=Field(default_factory=list,max_length=10000)
