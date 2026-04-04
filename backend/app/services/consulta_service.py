from __future__ import annotations

import unicodedata

from app.models import Tramite
from app.schemas.consulta import ConsultaMatch, ConsultaResponse


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
    description = best_match.descripcion or "Sin descripcion registrada."
    requirements = best_match.requisitos or "Sin requisitos registrados."
    cost = best_match.costo or "Sin costo registrado."
    schedule = best_match.horario or "Sin horario registrado."

    return (
        f"Encontre {total_matches} tramite(s) relacionado(s). "
        f"El tramite mas relevante es '{best_match.nombre}'. "
        f"Descripcion: {description} "
        f"Requisitos: {requirements} "
        f"Costo: {cost} "
        f"Horario: {schedule} "
        f"Dependencia responsable: {best_match.dependencia}."
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
            total_resultados=0,
            tramites_relacionados=[],
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
            total_resultados=0,
            tramites_relacionados=[],
        )

    matches = [tramite for _, tramite in scored_tramites[:3]]
    response_matches = [
        ConsultaMatch(
            id=tramite.id,
            nombre=tramite.nombre,
            slug=tramite.slug,
            dependencia=tramite.dependencia,
            fuente_url=tramite.fuente_url,
        )
        for tramite in matches
    ]

    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=_build_response_text(matches[0], len(scored_tramites)),
        total_resultados=len(scored_tramites),
        tramites_relacionados=response_matches,
    )
