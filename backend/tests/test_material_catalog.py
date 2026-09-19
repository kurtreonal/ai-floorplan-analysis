"""N1 catalog contract and isolated MySQL persistence."""
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import Material


@pytest.mark.parametrize("field,limit", [("code", 64), ("name", 255), ("unit", 32), ("category", 100)])
def test_bounded_required_fields(field, limit):
    for value in (None, "", " ", " padded", "bad\x00text", "x" * (limit + 1)):
        with pytest.raises(ValueError):
            Material(**{field: value})
    assert getattr(Material(**{field: "x" * limit}), field) == "x" * limit


def test_catalog_persistence_and_unique_code():
    engine = get_engine()
    assert engine.url.database == "ved_electrical_verify" and engine.url.username == "ved_test", "Use isolated test runner"
    Material.__table__.create(engine, checkfirst=True)
    Material.__table__.create(engine, checkfirst=True)
    assert "materials" in inspect(engine).get_table_names()
    assert not Material.__table__.foreign_keys
    assert "price" not in Material.__table__.columns
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                material = Material(code="N1-SYNTHETIC", name="Test item", unit="piece", category="Test")
                session.add(material)
                session.flush()
                assert material.is_active is True
                material.is_active = False
                session.flush()
                session.refresh(material)
                assert material.is_active is False
                with pytest.raises(IntegrityError), session.begin_nested():
                    session.add(Material(code=material.code, name="Duplicate", unit="meter", category="Test"))
                    session.flush()
        finally:
            transaction.rollback()
