from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator
from app.geometry.calibration import known_dimension_scale, PAPER_RULER_PREFIX, MEASURED_RULER_PREFIX
import json
import math


Elevation = Annotated[StrictInt | StrictFloat, Field(ge=-10000, le=10000, allow_inf_nan=False)]
Scale = Annotated[StrictInt | StrictFloat, Field(ge=0.000001, le=1000000, allow_inf_nan=False)]
Dimension = Annotated[StrictInt, Field(ge=1, le=100000)]


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_notes: str = Field(min_length=1, max_length=1000)


class ElevationInput(ApprovalInput):
    elevation_meters: Elevation | None


class KnownDimension(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pixel_length: Annotated[StrictInt | StrictFloat, Field(gt=0, le=150000, allow_inf_nan=False)]
    real_length_meters: Annotated[StrictInt | StrictFloat, Field(gt=0, le=100000, allow_inf_nan=False)]


class RulerPoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: Annotated[StrictInt | StrictFloat, Field(ge=0, le=100000, allow_inf_nan=False)]
    y: Annotated[StrictInt | StrictFloat, Field(ge=0, le=100000, allow_inf_nan=False)]


class PaperRuler(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: RulerPoint
    end: RulerPoint
    length_cm: Annotated[StrictInt | StrictFloat, Field(gt=0, le=100000, allow_inf_nan=False)]
    scale_denominator: Annotated[StrictInt | StrictFloat, Field(ge=1, le=100000, allow_inf_nan=False)]
    paper_size: Literal['A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'CUSTOM'] = 'A1'
    custom_width_mm: Annotated[StrictInt | StrictFloat, Field(gt=0, le=10000, allow_inf_nan=False)] | None = None
    custom_height_mm: Annotated[StrictInt | StrictFloat, Field(gt=0, le=10000, allow_inf_nan=False)] | None = None


class MeasuredRuler(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: RulerPoint
    end: RulerPoint
    length_meters: Annotated[StrictInt | StrictFloat, Field(gt=0, le=100000, allow_inf_nan=False)]


class ScaleInput(ApprovalInput):
    pixels_per_meter: Scale | None
    reference_width_pixels: Dimension | None
    reference_height_pixels: Dimension | None
    # Existing append-only approval stores the resulting scale and human-readable
    # measurement evidence; no new database field or historical rewrite needed.
    known_dimension: KnownDimension | None = Field(default=None, exclude=True)
    paper_ruler: PaperRuler | None = Field(default=None, exclude=True)
    measured_ruler: MeasuredRuler | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def complete_reference(self):
        if self.measured_ruler is not None:
            if self.known_dimension is not None or self.paper_ruler is not None or self.pixels_per_meter is not None:
                raise ValueError('Supply only one calibration method.')
            ruler=self.measured_ruler
            if self.reference_width_pixels is None or self.reference_height_pixels is None:
                raise ValueError('A ruler requires reference image dimensions.')
            if any(p.x>self.reference_width_pixels or p.y>self.reference_height_pixels for p in (ruler.start,ruler.end)):
                raise ValueError('Ruler endpoints must be inside the reference image.')
            self.pixels_per_meter=known_dimension_scale(math.hypot(ruler.end.x-ruler.start.x,ruler.end.y-ruler.start.y),ruler.length_meters)
            self.evidence_notes=MEASURED_RULER_PREFIX+json.dumps(ruler.model_dump(),separators=(',',':'))+'\n'+self.evidence_notes
            if len(self.evidence_notes)>1000:raise ValueError('Shorten ruler evidence notes.')
        if self.paper_ruler is not None:
            if self.known_dimension is not None or self.pixels_per_meter is not None:
                raise ValueError('Supply only one calibration method.')
            ruler = self.paper_ruler
            if self.reference_width_pixels is None or self.reference_height_pixels is None:
                raise ValueError('A ruler requires reference image dimensions.')
            if any(p.x > self.reference_width_pixels or p.y > self.reference_height_pixels
                   for p in (ruler.start, ruler.end)):
                raise ValueError('Ruler endpoints must be inside the reference image.')
            if ruler.paper_size == 'CUSTOM' and (ruler.custom_width_mm is None or ruler.custom_height_mm is None):
                raise ValueError('Custom paper requires both dimensions.')
            span = math.hypot(ruler.end.x-ruler.start.x, ruler.end.y-ruler.start.y)
            self.pixels_per_meter = known_dimension_scale(span, ruler.length_cm*ruler.scale_denominator/100)
            self.evidence_notes = (PAPER_RULER_PREFIX + json.dumps(ruler.model_dump(exclude_none=True), separators=(',', ':'))
                                   + '\n' + self.evidence_notes)
            if len(self.evidence_notes) > 1000:
                raise ValueError('Shorten ruler evidence notes.')
        if self.known_dimension is not None:
            reference = self.known_dimension
            measured = known_dimension_scale(reference.pixel_length, reference.real_length_meters)
            if self.pixels_per_meter is not None:
                raise ValueError('Supply a known dimension or an explicit scale, not both.')
            if self.reference_width_pixels is None or self.reference_height_pixels is None:
                raise ValueError('Known-dimension calibration requires reference image dimensions.')
            if reference.pixel_length > math.hypot(self.reference_width_pixels, self.reference_height_pixels):
                raise ValueError('Measured span cannot exceed the reference image diagonal.')
            self.pixels_per_meter = measured
            evidence = (f'Known dimension: {reference.pixel_length:g} source pixels = '
                        f'{reference.real_length_meters:g} metres. {self.evidence_notes}')
            if len(evidence) > 1000:
                raise ValueError('Shorten evidence notes to fit the calibration reference.')
            self.evidence_notes = evidence
        values = (self.pixels_per_meter, self.reference_width_pixels, self.reference_height_pixels)
        if any(value is None for value in values) and not all(value is None for value in values):
            raise ValueError("Scale and both reference dimensions must be supplied together.")
        return self


class ApprovalMetadata(BaseModel):
    revision_id: int | None
    state: Literal["unresolved", "approved"]
    evidence_notes: str | None
    reviewed_by_user_id: int | None
    created_at: datetime | None


class ElevationResponse(ApprovalMetadata):
    unit: Literal["meter"] = "meter"
    elevation_meters: float | None


class ScaleResponse(ApprovalMetadata):
    state: Literal['unresolved', 'approved', 'draft']
    unit: Literal["pixels_per_meter"] = "pixels_per_meter"
    pixels_per_meter: float | None
    reference_width_pixels: int | None
    reference_height_pixels: int | None


class PageSettingsResponse(BaseModel):
    floor_plan_id: int
    floor_plan_page_id: int
    page_number: int
    scale: ScaleResponse


class AnalysisSettingsResponse(BaseModel):
    project_floor_id: int
    elevation: ElevationResponse
    pages: list[PageSettingsResponse]
