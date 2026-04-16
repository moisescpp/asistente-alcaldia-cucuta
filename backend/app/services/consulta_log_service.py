from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConsultaLog
from app.schemas.consulta import ConsultaResponse


def infer_response_origin(response: ConsultaResponse) -> str:
    if response.mensaje_estado == "Coincidencias semanticas encontradas":
        return "semantica"
    if response.mensaje_estado == "Coincidencias encontradas":
        return "textual"
    if response.mensaje_estado == "Consulta demasiado general":
        return "clarificacion"
    if response.mensaje_estado == "Sin coincidencias en la base actual":
        return "sin_coincidencias"
    return "desconocido"


def log_consulta_result(
    db: Session,
    *,
    pregunta: str,
    response: ConsultaResponse,
) -> ConsultaLog:
    tramite_principal = response.tramite_principal
    log_entry = ConsultaLog(
        pregunta=pregunta,
        mensaje_estado=response.mensaje_estado,
        origen_respuesta=infer_response_origin(response),
        total_resultados=response.total_resultados,
        tramite_principal_id=tramite_principal.id if tramite_principal else None,
        tramite_principal_nombre=tramite_principal.nombre if tramite_principal else None,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def list_recent_consulta_logs(db: Session, *, limit: int = 50) -> list[ConsultaLog]:
    query = select(ConsultaLog).order_by(ConsultaLog.created_at.desc(), ConsultaLog.id.desc()).limit(limit)
    return db.scalars(query).all()
