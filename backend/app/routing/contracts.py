"""Metric routing inputs; heights and alignment are explicit designer choices."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Identifier = Annotated[int, Field(strict=True, gt=0)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Point(Contract):
    floor_id: Identifier
    x: Number
    y: Number
    elevation_meters: Number


class Endpoint(Contract):
    floor_id: Identifier
    # A target references an existing reviewed canonical symbol. A panel is
    # explicitly placed by the designer; neither is inferred from class names.
    symbol_id: str | None = None
    x: Number
    y: Number
    elevation_meters: Number
    wall_id: Identifier | None = None


class FloorConfig(Contract):
    floor_id: Identifier
    expected_layout_version: Identifier
    service_elevation_meters: Number
    offset_x: Number
    offset_y: Number


class Connector(Contract):
    id: Annotated[str, Field(min_length=1, max_length=100)]
    from_floor_id: Identifier
    to_floor_id: Identifier
    # Position in the explicitly aligned project metric plane.
    x: Number
    y: Number


class Obstacle(Contract):
    floor_id: Identifier
    min_x: Number
    min_y: Number
    max_x: Number
    max_y: Number
    bottom: Number
    top: Number

    @model_validator(mode="after")
    def ordered(self):
        if self.min_x >= self.max_x or self.min_y >= self.max_y or self.bottom >= self.top:
            raise ValueError("Obstacle bounds must be ordered.")
        return self


class RoutingRequest(Contract):
    floors: Annotated[list[FloorConfig], Field(min_length=1, max_length=8)]
    panel: Endpoint
    target: Endpoint
    connectors: Annotated[list[Connector], Field(max_length=32)] = []
    obstacles: Annotated[list[Obstacle], Field(max_length=128)] = []
    grid_step_meters: Annotated[float, Field(ge=0.1, le=5, allow_inf_nan=False)]
    alignment_confirmed: Literal[True]
    purpose: Literal["planning"] = "planning"

    @model_validator(mode="after")
    def references(self):
        ids = [floor.floor_id for floor in self.floors]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate floors.")
        if self.panel.floor_id not in ids or self.target.floor_id not in ids:
            raise ValueError("Endpoints require configured floors.")
        if not self.target.symbol_id or self.panel.symbol_id is not None:
            raise ValueError("A target symbol and an explicit panel are required.")
        if len({item.id for item in self.connectors}) != len(self.connectors):
            raise ValueError("Duplicate connectors.")
        for item in self.connectors:
            if item.from_floor_id not in ids or item.to_floor_id not in ids or item.from_floor_id == item.to_floor_id:
                raise ValueError("Invalid connector floor reference.")
        if any(item.floor_id not in ids for item in self.obstacles):
            raise ValueError("Invalid obstacle floor reference.")
        return self


class Segment(Contract):
    start: Point
    end: Point
    kind: Literal["ceiling_service", "wall_rise", "wall_drop", "riser"]
    horizontal_meters: Number
    vertical_meters: Number
    connector_id: str | None = None


class RouteResult(Contract):
    provenance: Literal["generated"] = "generated"
    algorithm: Literal["orthogonal_astar_v1"] = "orthogonal_astar_v1"
    points: list[Point]
    segments: list[Segment]
    horizontal_meters: Number
    vertical_meters: Number
    total_meters: Number
