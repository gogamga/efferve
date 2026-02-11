"""Shared test fixtures."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import efferve.database as db_module
from efferve.database import get_session
from efferve.main import app


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created.

    StaticPool ensures every session uses the same connection,
    so the in-memory database is shared across the test.
    """
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden DB engine and session."""
    # Patch the module-level engine so lifespan's init_db() and
    # _handle_beacon_event() both use the test engine.
    original_engine = db_module.engine
    db_module.engine = engine

    def _override_session() -> Generator[Session, None, None]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    db_module.engine = original_engine
