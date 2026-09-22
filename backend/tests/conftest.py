import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure database & model modules resolve regardless of CWD
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def db(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session_factory):
    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def register_user(client):
    """Return a helper that registers a tenant and logs in, returning auth headers + user data."""

    def _register(email: str, business: str = "Test Business"):
        payload = {
            "business_name": business,
            "email": email,
            "password": "StrongPass123!",
            "contact": "555-0100",
            "address": "1 Main St",
            "role": "business",
        }
        r = client.post("/api/auth/register", json=payload)
        assert r.status_code == 201, r.text
        login = client.post(
            "/api/auth/login",
            data={"username": email, "password": "StrongPass123!"},
        )
        assert login.status_code == 200, login.text
        data = login.json()
        return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]

    return _register


def seed_transaction(db, owner_id=None, item_id=None, item_name="Item", tx_type="sale", quantity=1.0, unit_price=1.0, days_ago=0, reference="test"):
    """Insert a transaction directly (back-datable) for history building."""
    from models.transaction import Transaction
    from datetime import datetime, timedelta
    tx = Transaction(
        owner_id=owner_id, item_id=item_id, item_name=item_name,
        transaction_type=tx_type, quantity=quantity, unit="units",
        unit_price=unit_price, reference=reference,
        transaction_date=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(tx)
    return tx