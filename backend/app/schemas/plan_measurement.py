from typing import Annotated,Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,StrictBool,StrictFloat,StrictInt,model_validator
from app.schemas.analysis_settings import MeasuredRuler

Length=Annotated[StrictFloat|StrictInt,Field(gt=0,le=1000,allow_inf_nan=False)]
Elevation=Annotated[StrictFloat|StrictInt,Field(ge=-10000,le=10000,allow_inf_nan=False)]


class PlanMeasurementInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    # Null means retain reliable source metadata; otherwise use the displayed
    # input defaults. Neither paper dimensions nor the nominal ratio calibrate.
    paper_size:Literal['A4','A3','A2','A1','A0']|None=None
    orientation:Literal['portrait','landscape']|None=None
    display_paper_size:Literal['ORIGINAL','A0','A1','A2','A3','A4','A5','CUSTOM']='ORIGINAL'
    display_orientation:Literal['portrait','landscape']|None=None
    display_width_mm:Annotated[StrictFloat|StrictInt,Field(gt=0,le=10000,allow_inf_nan=False)]|None=None
    display_height_mm:Annotated[StrictFloat|StrictInt,Field(gt=0,le=10000,allow_inf_nan=False)]|None=None
    scale_denominator:Annotated[StrictFloat|StrictInt,Field(ge=1,le=100000,allow_inf_nan=False)]=100
    measurement_method:Literal['auto','source_sheet','full_sheet','reference','estimated','not_to_scale']='auto'
    height_mode:Literal['automatic','custom']='custom'
    allow_estimated_scale:StrictBool=False
    applied_defaults_revision:Annotated[StrictInt,Field(ge=0)]|None=None
    source_paper_size:Literal['A0','A1','A2','A3','A4','A5','CUSTOM']='A1'
    source_orientation:Literal['portrait','landscape']|None=None
    source_width_mm:Annotated[StrictFloat|StrictInt,Field(gt=0,le=10000,allow_inf_nan=False)]|None=None
    source_height_mm:Annotated[StrictFloat|StrictInt,Field(gt=0,le=10000,allow_inf_nan=False)]|None=None
    full_sheet_confirmed:StrictBool=False
    drawing_scale_confirmed:StrictBool=False
    image_size_percent:Annotated[StrictFloat|StrictInt,Field(gt=0,le=100,allow_inf_nan=False)]=100
    reference:MeasuredRuler|None=None
    service_height_above_floor_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]|None=None
    fixture_center_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]|None=None
    fixture_connection_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]|None=None
    floor_elevation_meters:Elevation|None=None
    floor_to_ceiling_height_meters:Length|None=None
    service_elevation_meters:Elevation|None=None
    outlet_center_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]=.3
    switch_center_height_meters:Annotated[StrictFloat|StrictInt,Field(ge=0,le=100,allow_inf_nan=False)]=1.2

    @model_validator(mode='after')
    def custom_paper_dimensions(self):
        if self.display_paper_size=='CUSTOM' and (self.display_width_mm is None or self.display_height_mm is None):
            raise ValueError('Custom paper requires width and height.')
        if self.measurement_method in ('full_sheet','estimated') and self.source_paper_size=='CUSTOM' and (self.source_width_mm is None or self.source_height_mm is None):
            raise ValueError('Original custom sheet requires width and height.')
        if self.measurement_method=='full_sheet' and not self.full_sheet_confirmed:
            raise ValueError('Confirm that the complete original sheet is present.')
        if self.measurement_method=='reference' and self.reference is None:
            raise ValueError('Select two endpoints and enter their known length.')
        if self.height_mode=='automatic' and self.floor_to_ceiling_height_meters is None:
            raise ValueError('Automatic heights require a snapshotted ceiling height.')
        return self


class PlanMeasurementWrite(PlanMeasurementInput):
    use_automatic_setup:StrictBool=False
    processing_job_id:Annotated[StrictInt,Field(gt=0)]|None=None
    expected_revision:Annotated[StrictInt,Field(ge=0)]
    request_id:UUID


class PlanMeasurementResponse(BaseModel):
    floor_plan_id:Annotated[int,Field(gt=0)]
    revision:Annotated[int,Field(ge=0)]
    floor_elevation_meters:float|None=None
    settings:PlanMeasurementInput
    pages:list[dict]=Field(default_factory=list,max_length=10000)
    source_pages:list[dict]=Field(default_factory=list,max_length=10000)
    measurement_context:dict|None=None
    effective_measurement:dict|None=None
