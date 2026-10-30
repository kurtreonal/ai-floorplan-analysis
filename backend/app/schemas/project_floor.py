from pydantic import BaseModel, ConfigDict, Field
from app.services.layout_materials import LayoutType


class ProjectFloorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    layout_type: LayoutType | None = None


class ProjectFloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    sort_order: int
    layout_type: LayoutType | None = None
