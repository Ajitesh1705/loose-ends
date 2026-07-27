"""Test fixtures. DB tests run against the compose Postgres but are wrapped in an
outer transaction that is rolled back after each test, so they never mutate demo data.
Nested commits inside endpoints/services land on savepoints (join_transaction_mode).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.main import app


@pytest.fixture
def db_conn():
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture
def db(db_conn):
    session = Session(
        bind=db_conn,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
