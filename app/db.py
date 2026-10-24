"""Database engine, session factory and FastAPI dependency."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _ensure_sqlite_directory(url: str) -> None:
    """Create the parent folder for a file-based SQLite database."""
    if not url.startswith("sqlite:///"):
        return

    path = url.removeprefix("sqlite:///")
    if not path or path == ":memory:":
        return

    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """SQLite ignores foreign keys unless explicitly enabled per connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it afterwards."""
    with SessionLocal() as session:
        yield session
