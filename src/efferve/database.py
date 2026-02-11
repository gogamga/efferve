"""Database setup and session management."""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from efferve.config import settings

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI Depends()."""
    with Session(engine) as session:
        yield session
