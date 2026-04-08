from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tramite
from app.schemas.consulta import ConsultaMatch, ConsultaResponse
from app.services.embedding_service import generate_embedding, get_tramite_semantic_aliases
from app.services.rag_service import generate_rag_response


DEFAULT_SUGGESTIONS = [
    "Consulta por impuesto predial",
    "Consulta por facilidades de pago",
    "Consulta por devolucion o compensacion de pagos",
]

SEMANTIC_QUERY_LIMIT = 5
SEMANTIC_RESULT_LIMIT = 3
SEMANTIC_DISTANCE_THRESHOLD = 0.50
SEMANTIC_RELATED_DISTANCE_MARGIN = 0.08
GENERIC_QUERY_TOKENS = {
    "consulta",
    "consultar",
    "informacion",
    "informacion",
    "tramite",
    "tramites",
    "impuesto",
    "impuestos",
    "pago",
    "pagos",
    "sobre",
    "necesito",
    "quiero",
}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower().strip()


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


def _build_success_response(
    *,
    pregunta: str,
    tramites: list[Tramite],
    message_status: str,
) -> ConsultaResponse:
    tramite_principal = tramites[0]
    tramite_match = _build_match(tramite_principal)
    related_matches = [_build_match(tramite) for tramite in tramites[1:]]

    fallback_text = (
        f"Tramite principal: {tramite_principal.nombre}.\n"
        f"Dependencia: {tramite_principal.dependencia}.\n"
        f"Descripcion: {tramite_principal.descripcion or 'Sin descripcion registrada.'}\n"
        f"Requisitos: {tramite_principal.requisitos or 'Sin requisitos registrados.'}\n"
        f"Costo: {tramite_principal.costo or 'Sin costo registrado.'}\n"
        f"Horario: {tramite_principal.horario or 'Sin horario registrado.'}"
    )

    try:
        response_text = generate_rag_response(
            pregunta=pregunta,
            tramites=tramites,
        )
    except Exception:
        response_text = fallback_text

    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=response_text,
        mensaje_estado=message_status,
        total_resultados=len(tramites),
        tramite_principal=tramite_match,
        tramites_relacionados=related_matches,
        sugerencias=[],
    )


def _build_empty_response(pregunta: str) -> ConsultaResponse:
    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=(
            "No encontre un tramite directamente relacionado en la base actual. "
            "Prueba con una consulta mas especifica o usa una de las sugerencias."
        ),
        mensaje_estado="Sin coincidencias en la base actual",
        total_resultados=0,
        tramite_principal=None,
        tramites_relacionados=[],
        sugerencias=DEFAULT_SUGGESTIONS,
    )


def _text_match_metadata(pregunta: str, tramite: Tramite) -> tuple[int, int, bool]:
    normalized_question = _normalize_text(pregunta)
    tokens = [token for token in normalized_question.split() if len(token) > 2]
    specific_tokens = [token for token in tokens if token not in GENERIC_QUERY_TOKENS]

    searchable_text = " ".join(
        [
            _normalize_text(tramite.nombre),
            _normalize_text(tramite.descripcion),
            _normalize_text(tramite.requisitos),
            _normalize_text(tramite.costo),
            _normalize_text(tramite.horario),
            _normalize_text(tramite.dependencia),
            _normalize_text(" ".join(get_tramite_semantic_aliases(tramite))),
        ]
    )

    total_matches = sum(1 for token in tokens if token in searchable_text)
    specific_matches = sum(1 for token in specific_tokens if token in searchable_text)
    phrase_match = len(normalized_question) >= 5 and normalized_question in searchable_text

    return total_matches, specific_matches, phrase_match


def process_consulta_textual(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    scored_tramites: list[tuple[Tramite, int, int, bool]] = []
    for tramite in tramites:
        if not tramite.activo:
            continue

        total_matches, specific_matches, phrase_match = _text_match_metadata(
            pregunta,
            tramite,
        )

        if total_matches > 0 and (specific_matches > 0 or phrase_match):
            scored_tramites.append(
                (tramite, total_matches, specific_matches, phrase_match),
            )

    matched_tramites = [tramite for tramite, _, _, _ in scored_tramites]
    matched_tramites.sort(
        key=lambda candidate: next(
            (
                (
                    specific_matches,
                    total_matches,
                    1 if phrase_match else 0,
                )
                for tramite, total_matches, specific_matches, phrase_match in scored_tramites
                if tramite.id == candidate.id
            ),
            (0, 0, 0),
        ),
        reverse=True,
    )

    if not matched_tramites:
        return _build_empty_response(pregunta)

    return _build_success_response(
        pregunta=pregunta,
        tramites=matched_tramites[:SEMANTIC_RESULT_LIMIT],
        message_status="Coincidencias encontradas",
    )


def process_consulta_semantica(
    db: Session,
    pregunta: str,
) -> ConsultaResponse:
    embedding = generate_embedding(pregunta)

    distance_label = Tramite.embedding_vector.cosine_distance(embedding).label("distance")
    query = (
        select(Tramite, distance_label)
        .where(
            Tramite.activo.is_(True),
            Tramite.embedding_vector.is_not(None),
        )
        .order_by(distance_label)
        .limit(SEMANTIC_QUERY_LIMIT)
    )

    results = db.execute(query).all()

    if not results:
        return _build_empty_response(pregunta)

    best_tramite, best_distance = results[0]
    if best_distance is None or best_distance > SEMANTIC_DISTANCE_THRESHOLD:
        return _build_empty_response(pregunta)

    related_distance_limit = min(
        SEMANTIC_DISTANCE_THRESHOLD,
        best_distance + SEMANTIC_RELATED_DISTANCE_MARGIN,
    )

    filtered_tramites = [best_tramite]
    for tramite, distance in results[1:]:
        if distance is None:
            continue
        if distance <= related_distance_limit:
            filtered_tramites.append(tramite)

    filtered_tramites = filtered_tramites[:SEMANTIC_RESULT_LIMIT]

    if not filtered_tramites:
        return _build_empty_response(pregunta)

    return _build_success_response(
        pregunta=pregunta,
        tramites=filtered_tramites,
        message_status="Coincidencias semanticas encontradas",
    )


def process_consulta(
    db: Session,
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    has_semantic_data = any(
        tramite.activo and tramite.embedding_vector is not None for tramite in tramites
    )

    if has_semantic_data:
        try:
            semantic_response = process_consulta_semantica(db, pregunta)
            if semantic_response.total_resultados > 0:
                return semantic_response

            textual_response = process_consulta_textual(pregunta, tramites)
            if textual_response.total_resultados > 0:
                return textual_response

            return semantic_response
        except Exception:
            return process_consulta_textual(pregunta, tramites)

    return process_consulta_textual(pregunta, tramites)
