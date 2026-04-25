from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from app.services.embedding_service import get_tramite_semantic_aliases

GENERIC_DESCRIPTION_PATTERNS = (
    "consulta orientativa",
    "tramite de prueba",
    "sin descripcion",
    "no hay descripcion",
    "tramite para",
    "proceso para",
)

HACIENDA_KEYWORDS = {
    "hacienda",
    "rentas",
    "impuestos",
    "tributario",
    "tributaria",
    "predial",
    "industria",
    "comercio",
    "alumbrado",
    "espectaculos",
    "devolucion",
    "compensacion",
    "paz",
    "salvo",
}


@dataclass
class TramiteQualityReport:
    score: int
    level: str
    alerts: list[str]
    blocking_issues: list[str]
    scope_status: str
    recommended_action: str


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _word_count(value: str | None) -> int:
    normalized = _normalize_text(value)
    return len([token for token in normalized.split() if token])


def _has_tax_context(payload: dict[str, Any]) -> bool:
    searchable = _normalize_text(
        " ".join(
            [
                str(payload.get("nombre") or ""),
                str(payload.get("descripcion") or ""),
                str(payload.get("dependencia") or ""),
                str(payload.get("requisitos") or ""),
            ]
        )
    )
    return any(keyword in searchable for keyword in HACIENDA_KEYWORDS)


def _extract_alias_count(payload_or_tramite: Any) -> int:
    try:
        return len(get_tramite_semantic_aliases(payload_or_tramite))
    except Exception:
        return 0


def _coerce_payload(payload_or_tramite: Any) -> dict[str, Any]:
    if isinstance(payload_or_tramite, dict):
        return payload_or_tramite

    return {
        "nombre": getattr(payload_or_tramite, "nombre", ""),
        "slug": getattr(payload_or_tramite, "slug", ""),
        "descripcion": getattr(payload_or_tramite, "descripcion", ""),
        "requisitos": getattr(payload_or_tramite, "requisitos", ""),
        "costo": getattr(payload_or_tramite, "costo", ""),
        "horario": getattr(payload_or_tramite, "horario", ""),
        "dependencia": getattr(payload_or_tramite, "dependencia", ""),
        "fuente_url": getattr(payload_or_tramite, "fuente_url", ""),
        "embedding_vector": getattr(payload_or_tramite, "embedding_vector", None),
    }


def assess_tramite_quality(payload_or_tramite: Any) -> TramiteQualityReport:
    payload = _coerce_payload(payload_or_tramite)

    score = 100
    alerts: list[str] = []
    blocking_issues: list[str] = []

    description = str(payload.get("descripcion") or "")
    requirements = str(payload.get("requisitos") or "")
    source_url = str(payload.get("fuente_url") or "")
    dependency = str(payload.get("dependencia") or "")
    embedding_vector = payload.get("embedding_vector")

    description_words = _word_count(description)
    requirement_words = _word_count(requirements)
    alias_count = _extract_alias_count(payload_or_tramite)
    has_tax_context = _has_tax_context(payload)

    if description_words == 0:
        score -= 40
        message = "Agrega una descripcion clara del tramite."
        alerts.append(message)
        blocking_issues.append(message)
    elif description_words < 12:
        score -= 24
        message = "La descripcion es demasiado corta para una consulta ciudadana."
        alerts.append(message)
        blocking_issues.append(message)
    elif description_words < 20:
        score -= 10
        alerts.append("La descripcion todavia puede ser mas especifica.")

    normalized_description = _normalize_text(description)
    if any(pattern in normalized_description for pattern in GENERIC_DESCRIPTION_PATTERNS):
        score -= 18
        message = "La descripcion suena generica; explica mejor para que sirve el tramite."
        alerts.append(message)
        blocking_issues.append(message)

    if requirement_words == 0:
        score -= 14
        message = "Agrega requisitos reales del tramite."
        alerts.append(message)
        blocking_issues.append(message)
    elif requirement_words < 6:
        score -= 8
        message = "Los requisitos son muy cortos y pueden quedarse sin contexto."
        alerts.append(message)
        blocking_issues.append(message)

    if not source_url:
        score -= 8
        alerts.append("Falta la fuente oficial del tramite.")

    if not dependency:
        score -= 6
        alerts.append("Falta la dependencia responsable.")

    if dependency and not has_tax_context:
        score -= 10
        alerts.append("Este tramite no muestra contexto claro de rentas e impuestos.")

    if embedding_vector is None and "embedding_vector" in payload:
        score -= 10
        alerts.append("Este tramite aun no tiene embedding actualizado.")

    if alias_count < 3:
        score -= 10
        alerts.append("El tramite tiene pocas senales semanticas para lenguaje ciudadano.")
    elif alias_count < 6:
        score -= 4
        alerts.append("El tramite podria beneficiarse de mas contexto ciudadano.")

    score = max(score, 0)
    if score >= 85:
        level = "fuerte"
    elif score >= 70:
        level = "estable"
    elif score >= 55:
        level = "en_riesgo"
    else:
        level = "critico"

    if dependency and not has_tax_context:
        scope_status = "fuera_de_foco"
        recommended_action = (
            "Revisa si este tramite debe seguir activo en Hacienda o si conviene "
            "moverlo a otro catalogo institucional."
        )
    elif not dependency:
        scope_status = "sin_contexto"
        recommended_action = (
            "Completa la dependencia y el contexto tributario para que el panel "
            "pueda clasificar mejor este tramite."
        )
    elif level in {"critico", "en_riesgo"}:
        scope_status = "tributario"
        recommended_action = (
            "Fortalece descripcion, requisitos y fuente oficial para que el "
            "asistente responda con mas precision."
        )
    else:
        scope_status = "tributario"
        recommended_action = (
            "La base semantica va bien; solo conviene vigilar cambios futuros del "
            "catalogo y mantener el contenido actualizado."
        )

    deduped_alerts = list(dict.fromkeys(alerts))
    deduped_blocking = list(dict.fromkeys(blocking_issues))
    return TramiteQualityReport(
        score=score,
        level=level,
        alerts=deduped_alerts,
        blocking_issues=deduped_blocking,
        scope_status=scope_status,
        recommended_action=recommended_action,
    )


def validate_tramite_payload(payload_or_tramite: Any) -> list[str]:
    return assess_tramite_quality(payload_or_tramite).blocking_issues
