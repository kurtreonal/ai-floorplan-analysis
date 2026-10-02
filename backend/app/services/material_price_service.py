"""Price changes append history; the caller owns commit/rollback."""
from datetime import datetime, timezone

from app.repositories import material_price_repository as repository
from app.schemas.material_price import MaterialPriceWrite


class MaterialPriceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def update_material_price(session, *, current_user, material_id, request: MaterialPriceWrite):
    if getattr(getattr(current_user, "role", None), "name", None) != "ADMIN":
        raise MaterialPriceError("AUTHORIZATION_DENIED")
    material = repository.lock_material(session, material_id)
    if material is None:
        raise MaterialPriceError("MATERIAL_NOT_FOUND")
    if not material.is_active:
        raise MaterialPriceError("MATERIAL_INACTIVE")
    effective = request.effective_at.replace(tzinfo=None)
    if effective > datetime.now(timezone.utc).replace(tzinfo=None):
        raise MaterialPriceError("FUTURE_PRICE_NOT_SUPPORTED")
    previous = repository.last_revision(session, material_id)
    if previous and effective < previous.effective_at:
        raise MaterialPriceError("PRICE_EFFECTIVE_TIME_PRECEDES_CURRENT")
    if previous and (previous.unit_price, previous.currency, previous.unit, previous.effective_at) == (
            request.unit_price, request.currency, material.unit, effective):
        return previous
    return repository.append_price(session, material_id=material_id,
        version_number=previous.version_number + 1 if previous else 1,
        unit_price=request.unit_price, currency=request.currency, unit=material.unit,
        effective_at=effective, changed_by_user_id=current_user.id)
