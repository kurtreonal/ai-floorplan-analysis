from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import Estimate, EstimateItem, Material, MaterialPrice, Project, Role, User
from app.schemas.material_price import MaterialPriceWrite
from app.services.material_price_service import update_material_price


def test_mysql_estimate_snapshot_and_constraints():
    engine = get_engine()
    assert engine.url.database == "ved_electrical_verify" and engine.url.username == "ved_test"
    for _ in range(2):
        Estimate.__table__.create(engine, checkfirst=True)
        EstimateItem.__table__.create(engine, checkfirst=True)
    assert {"estimates", "estimate_items"} <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                admin = User(oauth_provider="test", oauth_subject=uuid4().hex,
                             role=session.scalar(select(Role).where(Role.name == "ADMIN")))
                project = Project(owner=admin, name="Synthetic estimate")
                material = Material(code=uuid4().hex, name="Synthetic item", unit="piece", category="Test")
                session.add_all([admin, project, material])
                session.flush()
                price_request = MaterialPriceWrite(unit_price="1.2345", currency="PHP",
                    effective_at=datetime.now(timezone.utc) - timedelta(seconds=2))
                update_material_price(session, current_user=admin, material_id=material.id, request=price_request)
                estimate = Estimate(project_id=project.id, version_number=1, created_by_user_id=admin.id,
                                    currency="PHP", total=Decimal("3.08625000"))
                session.add(estimate)
                session.flush()
                values = dict(estimate_id=estimate.id, line_number=1, material_id=material.id,
                    material_code=material.code, material_name=material.name, quantity=Decimal("2.5"),
                    unit="piece", captured_unit_price=Decimal("1.2345"), line_total=Decimal("3.08625000"))
                item = EstimateItem(**values)
                session.add(item)
                session.flush()
                update_material_price(session, current_user=admin, material_id=material.id,
                    request=MaterialPriceWrite(unit_price="99", currency="PHP",
                        effective_at=price_request.effective_at + timedelta(seconds=1)))
                material.name = "Changed catalog name"
                session.flush()
                session.refresh(item)
                session.refresh(estimate)
                assert item.captured_unit_price == Decimal("1.2345")
                assert item.quantity == Decimal("2.5")
                assert item.line_total == estimate.total == Decimal("3.08625000")
                assert item.material_name == "Synthetic item"
                assert item.unit == "piece"
                assert len(session.scalars(select(MaterialPrice).where(MaterialPrice.material_id == material.id)).all()) == 2
                for invalid in ({}, {"line_number": 0}, {"line_number": 2, "quantity": -1},
                                {"line_number": 2, "captured_unit_price": -1},
                                {"line_number": 2, "line_total": -1}, {"line_number": 2, "unit": ""},
                                {"line_number": 2, "estimate_id": -1}):
                    with pytest.raises((IntegrityError, OperationalError)) as error, session.begin_nested():
                        session.add(EstimateItem(**{**values, **invalid}))
                        session.flush()
                    assert error.value.orig.args[0] in {1062, 1452, 4025}
                for invalid in ({}, {"version_number": 0}, {"version_number": 2, "total": -1},
                                {"version_number": 2, "project_id": -1}):
                    with pytest.raises((IntegrityError, OperationalError)) as error, session.begin_nested():
                        session.add(Estimate(**{ "project_id": project.id, "version_number": 1,
                            "created_by_user_id": admin.id, "currency": "PHP", "total": 0, **invalid}))
                        session.flush()
                    assert error.value.orig.args[0] in {1062, 1452, 4025}
        finally:
            transaction.rollback()
