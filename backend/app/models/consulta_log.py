from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConsultaLog(Base):
    __tablename__ = "consulta_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pregunta: Mapped[str] = mapped_column(Text, nullable=False)
    mensaje_estado: Mapped[str] = mapped_column(String(120), nullable=False)
    origen_respuesta: Mapped[str] = mapped_column(String(40), nullable=False)
    total_resultados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tramite_principal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tramite_principal_nombre: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    resumen_respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    sugerencias_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    tramites_relacionados_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
