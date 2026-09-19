from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

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
