from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base


class Tramite(Base):
    __tablename__ = "tramites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    requisitos: Mapped[str | None] = mapped_column(Text, nullable=True)
    costo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    horario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dependencia: Mapped[str] = mapped_column(String(255), nullable=False)
    fuente_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Reservado para la recuperacion semantica de la Iteracion 3, cuando la
    # integracion con OpenAI pueda ejecutarse con facturacion habilitada.
    embedding_vector: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
