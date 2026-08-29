from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


DatabaseId = Annotated[int, Field(gt=0, le=9_223_372_036_854_775_807)]
ModelClassId = Annotated[int, Field(ge=0, le=2_147_483_647)]
SymbolLegendName = Annotated[str, Field(min_length=1, max_length=255)]


class SymbolLegendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: DatabaseId
    class_id: ModelClassId
    name: SymbolLegendName
