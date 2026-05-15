from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base


engine = create_engine(settings.sqlalchemy_database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_database_url() -> str:
    return settings.sqlalchemy_database_url


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
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS dirigido_a TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS pasos TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS tiempo_estimado TEXT"
            )
        )
        if engine.dialect.name == "postgresql":
            connection.execute(
                text(
                    "ALTER TABLE tramites "
                    "ALTER COLUMN tiempo_estimado TYPE TEXT"
                )
            )
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS medio_seguimiento TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS normatividad TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE tramites "
                "ADD COLUMN IF NOT EXISTS enlace_click_aqui VARCHAR(500)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE consulta_logs "
                "ADD COLUMN IF NOT EXISTS resumen_respuesta TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE consulta_logs "
                "ADD COLUMN IF NOT EXISTS sugerencias_texto TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE consulta_logs "
                "ADD COLUMN IF NOT EXISTS tramites_relacionados_texto TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE consulta_logs "
                "ADD COLUMN IF NOT EXISTS response_time_ms INTEGER"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS admin_session_state ("
                "id VARCHAR(50) PRIMARY KEY, "
                "active_session_id VARCHAR(120) NOT NULL, "
                "updated_at INTEGER NOT NULL"
                ")"
            )
        )
