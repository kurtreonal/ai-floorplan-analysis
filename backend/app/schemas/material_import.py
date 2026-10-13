from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class MaterialImportSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    file_sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    expected_versions: Annotated[dict[str, Annotated[int, Field(strict=True, ge=0)]], Field(min_length=1, max_length=5000)]
    confirmed: Literal[True]


class ImportRow(BaseModel):
    row_id: str
    sheet: str
    row: int
    code: str
    name: str
    unit: str
    category: str
    unit_price: str
    current_price: str | None
    current_currency: str | None
    version: int
    eligible: bool
    reason: str | None


class ImportPreview(BaseModel):
    file_sha256: str
    rows: list[ImportRow]
    issues: list[dict[str, str]]


class ImportResult(BaseModel):
    file_sha256: str
    created: int
    updated: int
    unchanged: int
