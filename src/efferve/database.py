"""Database setup and session management."""

from sqlmodel import Session, SQLModel, create_engine

from efferve.config import settings

engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)


def init_db() -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get a database session."""
    return Session(engine)
