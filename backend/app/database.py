from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_database_url() -> str:
    return settings.database_url


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_database_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS alias_ciudadanos TEXT"
            )
        )
