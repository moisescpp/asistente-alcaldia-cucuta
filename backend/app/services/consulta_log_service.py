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


def _extract_response_summary(response_text: str) -> str:
    if not response_text:
        return ""

    summary = response_text.split("\n\nTramite principal:", 1)[0].strip()
    return summary or response_text.strip()


def _serialize_lines(values: list[str]) -> str | None:
    cleaned_values = [value.strip() for value in values if value and value.strip()]
    if not cleaned_values:
        return None
    return "\n".join(cleaned_values)


def _deserialize_lines(values_text: str | None) -> list[str]:
    if not values_text:
        return []
    return [value.strip() for value in values_text.splitlines() if value.strip()]


def log_consulta_result(
    db: Session,
    *,
    pregunta: str,
    response: ConsultaResponse,
    response_time_ms: int | None = None,
) -> ConsultaLog:
    tramite_principal = response.tramite_principal
    log_entry = ConsultaLog(
        pregunta=pregunta,
        mensaje_estado=response.mensaje_estado,
        origen_respuesta=infer_response_origin(response),
        total_resultados=response.total_resultados,
        response_time_ms=response_time_ms,
        tramite_principal_id=tramite_principal.id if tramite_principal else None,
        tramite_principal_nombre=tramite_principal.nombre if tramite_principal else None,
        resumen_respuesta=_extract_response_summary(response.respuesta),
        sugerencias_texto=_serialize_lines(response.sugerencias),
        tramites_relacionados_texto=_serialize_lines(
            [tramite.nombre for tramite in response.tramites_relacionados]
        ),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def list_recent_consulta_logs(db: Session, *, limit: int = 50) -> list[ConsultaLog]:
    query = select(ConsultaLog).order_by(ConsultaLog.created_at.desc(), ConsultaLog.id.desc()).limit(limit)
    logs = db.scalars(query).all()

    for log in logs:
        setattr(log, "sugerencias", _deserialize_lines(log.sugerencias_texto))
        setattr(
            log,
            "tramites_relacionados",
            _deserialize_lines(log.tramites_relacionados_texto),
        )

    return logs
