from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.project_pricing import StrictModel, Identifier


class ItemPriceBinding(StrictModel):
    item_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    price_row_id: str | None = Field(default=None, min_length=1, max_length=120)
    material_id: Identifier | None = None


class ItemPriceSelection(StrictModel):
    price_version_id: Identifier
    price_row_id: str | None = Field(default=None, min_length=1, max_length=120)
    scope: Literal['floor', 'project']
    floor_id: Identifier | None = None
    mode: Literal['selected', 'all_wiring'] = 'selected'
    item_keys: list[str] = Field(default_factory=list, max_length=10000)
    bindings: list[ItemPriceBinding] = Field(default_factory=list, max_length=10000)

    @model_validator(mode='after')
    def scope_and_items(self):
        if (self.scope == 'floor') != (self.floor_id is not None):
            raise ValueError('Choose a floor for floor scope only.')
        if self.bindings:
            if self.item_keys or self.price_row_id or len({b.item_key for b in self.bindings}) != len(self.bindings):
                raise ValueError('Use distinct item bindings, without a separate single-price selection.')
        elif self.price_row_id is None:
            raise ValueError('Choose a price entry or per-item bindings.')
        if not self.bindings and self.mode == 'selected' and (not self.item_keys or len(set(self.item_keys)) != len(self.item_keys)):
            raise ValueError('Select distinct existing items.')
        if any(len(key) != 64 or any(c not in '0123456789abcdef' for c in key) for key in self.item_keys):
            raise ValueError('Invalid item identity.')
        if self.mode == 'all_wiring' and self.item_keys:
            raise ValueError('Apply-all scope is resolved by the server.')
        return self


class ItemPriceApply(ItemPriceSelection):
    request_id: UUID
    preview_token: str = Field(pattern=r'^[a-f0-9]{64}$')
