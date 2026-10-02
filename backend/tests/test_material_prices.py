from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import Material, MaterialPrice, Role, User
from app.repositories.material_price_repository import latest_price, price_history
from app.schemas.material_price import MaterialPriceWrite
from app.services.material_price_service import MaterialPriceError, update_material_price


@pytest.fixture
def context():
    engine = get_engine()
    assert engine.url.database == "ved_electrical_verify" and engine.url.username == "ved_test"
    MaterialPrice.__table__.create(engine, checkfirst=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                roles = {r.name: r for r in session.scalars(select(Role))}
                admin = User(oauth_provider="test", oauth_subject=uuid4().hex,
                             role=roles["ADMIN"])
                designer = User(oauth_provider="test", oauth_subject=uuid4().hex,
                                role=roles["DESIGNER"])
                material = Material(code=uuid4().hex, name="Synthetic", unit="piece", category="Test")
                session.add_all([admin, designer, material])
                session.flush()
                yield session, admin, designer, material
        finally:
            transaction.rollback()


def request(amount="12.3456", when=None):
    return MaterialPriceWrite(unit_price=amount, currency="PHP",
                              effective_at=when or datetime.now(timezone.utc) - timedelta(seconds=2))


def test_revision_history_current_price_and_noop(context):
    session, admin, _, material = context
    first_request = request()
    first = update_material_price(session, current_user=admin, material_id=material.id, request=first_request)
    assert update_material_price(session, current_user=admin, material_id=material.id, request=first_request).id == first.id
    second = update_material_price(session, current_user=admin, material_id=material.id,
                                   request=request("20", first_request.effective_at + timedelta(seconds=1)))
    assert second.version_number == 2
    session.expire_all()
    history = price_history(session, material.id)
    assert [p.unit_price for p in history] == [Decimal("12.3456"), Decimal("20")]
    assert all(p.changed_by_user_id == admin.id and p.unit == "piece" for p in history)
    assert latest_price(session, material.id, at=datetime.now(timezone.utc).replace(tzinfo=None)).id == second.id
    assert latest_price(session, material.id, at=first.effective_at).id == first.id


def test_denied_inactive_and_out_of_order(context):
    session, admin, designer, material = context
    with pytest.raises(MaterialPriceError, match="AUTHORIZATION_DENIED"):
        update_material_price(session, current_user=designer, material_id=material.id, request=request())
    first = request()
    update_material_price(session, current_user=admin, material_id=material.id, request=first)
    for when, code in [(first.effective_at - timedelta(days=1), "PRECEDES_CURRENT"),
                       (datetime.now(timezone.utc) + timedelta(days=1), "FUTURE_PRICE")]:
        with pytest.raises(MaterialPriceError, match=code):
            update_material_price(session, current_user=admin, material_id=material.id, request=request(when=when))
    material.is_active = False
    with pytest.raises(MaterialPriceError, match="MATERIAL_INACTIVE"):
        update_material_price(session, current_user=admin, material_id=material.id, request=request())
    assert len(price_history(session, material.id)) == 1


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "0.00001", "1000000000000"])
def test_invalid_prices(amount):
    with pytest.raises(ValidationError):
        request(amount)


def test_timezone_and_currency_required():
    with pytest.raises(ValidationError):
        request(when=datetime.now())
    with pytest.raises(ValidationError):
        MaterialPriceWrite(unit_price="1", currency="", effective_at=datetime.now(timezone.utc))
