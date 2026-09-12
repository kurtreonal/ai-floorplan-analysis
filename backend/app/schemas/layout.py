from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, UUID4


MAXIMUM_DATABASE_ID = 9_223_372_036_854_775_807
MAXIMUM_SAFE_INTEGER = 9_007_199_254_740_991
MAXIMUM_VERSION_NUMBER = 2_147_483_647

DatabaseId = Annotated[StrictInt, Field(gt=0, le=MAXIMUM_DATABASE_ID)]
SafePositiveInteger = Annotated[StrictInt, Field(gt=0, le=MAXIMUM_SAFE_INTEGER)]
SafeNonNegativeInteger = Annotated[
    StrictInt,
    Field(ge=0, le=MAXIMUM_SAFE_INTEGER),
]
SafeInteger = Annotated[
    StrictInt,
    Field(ge=-MAXIMUM_SAFE_INTEGER, le=MAXIMUM_SAFE_INTEGER),
]
FiniteNumber = Annotated[
    StrictInt | StrictFloat,
    Field(allow_inf_nan=False),
]
PositiveNumber = Annotated[
    StrictInt | StrictFloat,
    Field(gt=0, allow_inf_nan=False),
]
NonNegativeNumber = Annotated[
    StrictInt | StrictFloat,
    Field(ge=0, allow_inf_nan=False),
]


class LayoutSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LayoutPoint(LayoutSchema):
    x: NonNegativeNumber
    y: NonNegativeNumber


class LayoutFloor(LayoutSchema):
    project_floor_id: SafePositiveInteger
    name: Annotated[str, Field(min_length=1, max_length=100)]
    sort_order: SafeInteger
    elevation_meters: FiniteNumber


class LayoutCoordinateSystem(LayoutSchema):
    unit: Literal["meter"]
    origin: Literal["image_top_left"]
    x_direction: Literal["right"]
    y_direction: Literal["down"]
    pixels_per_meter: PositiveNumber
    image_width_pixels: Annotated[StrictInt, Field(gt=0, le=4096)]
    image_height_pixels: Annotated[StrictInt, Field(gt=0, le=4096)]
    width_meters: PositiveNumber
    height_meters: PositiveNumber


class LayoutWall(LayoutSchema):
    id: SafePositiveInteger
    source_candidate_id: SafePositiveInteger | None
    processing_job_id: SafePositiveInteger | None
    status: Literal["detected", "verified"]
    start: LayoutPoint
    end: LayoutPoint
    length_meters: NonNegativeNumber
    angle_degrees: Annotated[
        StrictInt | StrictFloat,
        Field(ge=0, lt=180, allow_inf_nan=False),
    ]
    thickness_meters: PositiveNumber | None
    height_meters: PositiveNumber | None


class LayoutRoom(LayoutSchema):
    id: SafePositiveInteger
    name: Annotated[str, Field(min_length=1, max_length=255)] | None
    boundary: Annotated[list[LayoutPoint], Field(min_length=3)]


class LayoutSymbolClass(LayoutSchema):
    id: SafeNonNegativeInteger
    name: Annotated[str, Field(min_length=1, max_length=255)]


class LayoutSymbol(LayoutSchema):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_alias=True,
        validate_by_name=False,
        serialize_by_alias=True,
    )

    id: Annotated[str, Field(min_length=1)]
    source_type: Literal["detected", "manual"]
    source_record_id: SafePositiveInteger
    processing_job_id: SafePositiveInteger
    status: Literal["confirmed", "manually_added"]
    symbol_class: LayoutSymbolClass = Field(alias="class")
    position: LayoutPoint


class LayoutRoutePoint(LayoutSchema):
    project_floor_id: SafePositiveInteger
    x: NonNegativeNumber
    y: NonNegativeNumber
    elevation_meters: FiniteNumber


class LayoutRoute(LayoutSchema):
    id: SafePositiveInteger
    points: Annotated[list[LayoutRoutePoint], Field(min_length=2)]


class CanonicalGeometryRequest(LayoutSchema):
    schema_version: Literal[1]
    project_id: SafePositiveInteger
    floor: LayoutFloor
    floor_plan_id: SafePositiveInteger
    coordinate_system: LayoutCoordinateSystem
    walls: list[LayoutWall]
    rooms: list[LayoutRoom]
    symbols: list[LayoutSymbol]
    routes: list[LayoutRoute]


class LayoutSaveRequest(LayoutSchema):
    expected_version_number: (
        Annotated[StrictInt, Field(gt=0, le=MAXIMUM_VERSION_NUMBER)] | None
    )
    idempotency_key: UUID4
    geometry: CanonicalGeometryRequest


class LayoutResponse(LayoutSchema):
    id: DatabaseId
    project_id: DatabaseId
    project_floor_id: DatabaseId
    floor_plan_id: DatabaseId
    version_number: Annotated[StrictInt, Field(gt=0, le=MAXIMUM_VERSION_NUMBER)]
    schema_version: Literal[1]
    is_current: Literal[True]
    created_at: datetime
    geometry: CanonicalGeometryRequest
    extension: dict[str, object] | None = None
