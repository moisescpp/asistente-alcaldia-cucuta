from __future__ import annotations

import unicodedata

from app.models import Tramite
from app.schemas.consulta import ConsultaMatch, ConsultaResponse

DEFAULT_SUGGESTIONS = [
    "Consulta por impuesto predial unificado",
    "Pregunta por facilidades de pago",
    "Pregunta por devolucion de pagos en exceso",
]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _build_haystack(tramite: Tramite) -> str:
    parts = [
        tramite.nombre,
        tramite.descripcion or "",
        tramite.requisitos or "",
        tramite.costo or "",
        tramite.horario or "",
        tramite.dependencia,
    ]
    return _normalize_text(" ".join(parts))


def _score_tramite(tramite: Tramite, tokens: list[str]) -> int:
    haystack = _build_haystack(tramite)
    score = 0

    for token in tokens:
        if token in haystack:
            score += 1

    normalized_name = _normalize_text(tramite.nombre)
    normalized_slug = _normalize_text(tramite.slug.replace("-", " "))

    for token in tokens:
        if token in normalized_name:
            score += 2
        if token in normalized_slug:
            score += 1

    return score


def _build_response_text(best_match: Tramite, total_matches: int) -> str:
    return (
        f"Encontre {total_matches} tramite(s) relacionado(s). "
        f"El tramite mas relevante es '{best_match.nombre}', gestionado por "
        f"{best_match.dependencia}. Revisa sus requisitos, costo y horario "
        "para orientarte antes de acudir al punto de atencion."
    )


def _build_match(tramite: Tramite) -> ConsultaMatch:
    return ConsultaMatch(
        id=tramite.id,
        nombre=tramite.nombre,
        slug=tramite.slug,
        descripcion=tramite.descripcion,
        requisitos=tramite.requisitos,
        costo=tramite.costo,
        horario=tramite.horario,
        dependencia=tramite.dependencia,
        fuente_url=tramite.fuente_url,
    )


def process_consulta(pregunta: str, tramites: list[Tramite]) -> ConsultaResponse:
    normalized_question = _normalize_text(pregunta)
    tokens = [token for token in normalized_question.split() if len(token) >= 3]

    if not tokens:
        return ConsultaResponse(
            pregunta=pregunta,
            respuesta=(
                "La consulta es demasiado corta. Intenta incluir el nombre del tramite "
                "o una palabra clave como impuesto, predial, pago o devolucion."
            ),
            mensaje_estado="Consulta demasiado corta",
            total_resultados=0,
            tramite_principal=None,
            tramites_relacionados=[],
            sugerencias=DEFAULT_SUGGESTIONS,
        )

    scored_tramites = []
    for tramite in tramites:
        score = _score_tramite(tramite, tokens)
        if score > 0:
            scored_tramites.append((score, tramite))

    scored_tramites.sort(key=lambda item: (-item[0], item[1].nombre))

    if not scored_tramites:
        return ConsultaResponse(
            pregunta=pregunta,
            respuesta=(
                "No encontre tramites relacionados con tu consulta en la base actual. "
                "Intenta usar otras palabras clave o revisa si el tramite pertenece a otro proceso."
            ),
            mensaje_estado="Sin coincidencias en la base actual",
            total_resultados=0,
            tramite_principal=None,
            tramites_relacionados=[],
            sugerencias=DEFAULT_SUGGESTIONS,
        )

    matches = [tramite for _, tramite in scored_tramites[:3]]
    response_matches = [_build_match(tramite) for tramite in matches]
    best_match = matches[0]

    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=_build_response_text(best_match, len(scored_tramites)),
        mensaje_estado="Coincidencias encontradas",
        total_resultados=len(scored_tramites),
        tramite_principal=_build_match(best_match),
        tramites_relacionados=response_matches,
        sugerencias=[],
    )
