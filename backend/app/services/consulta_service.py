from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tramite
from app.schemas.consulta import ConsultaMatch, ConsultaResponse
from app.services.embedding_service import generate_embedding
from app.services.rag_service import generate_rag_response


DEFAULT_SUGGESTIONS = [
    "Consulta por impuesto predial",
    "Consulta por facilidades de pago",
    "Consulta por devolucion o compensacion de pagos",
]

SEMANTIC_RESULT_LIMIT = 3
SEMANTIC_DISTANCE_THRESHOLD = 0.55


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


def _text_match_score(pregunta: str, tramite: Tramite) -> int:
    normalized_question = _normalize_text(pregunta)
    tokens = [token for token in normalized_question.split() if len(token) > 2]

    searchable_text = " ".join(
        [
            _normalize_text(tramite.nombre),
            _normalize_text(tramite.descripcion),
            _normalize_text(tramite.requisitos),
            _normalize_text(tramite.costo),
            _normalize_text(tramite.horario),
            _normalize_text(tramite.dependencia),
        ]
    )

    return sum(1 for token in tokens if token in searchable_text)


def process_consulta_textual(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    scored_tramites = [
        (tramite, _text_match_score(pregunta, tramite))
        for tramite in tramites
        if tramite.activo
    ]

    matched_tramites = [tramite for tramite, score in scored_tramites if score > 0]
    matched_tramites.sort(
        key=lambda tramite: _text_match_score(pregunta, tramite),
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
        .limit(SEMANTIC_RESULT_LIMIT)
    )

    results = db.execute(query).all()

    filtered_tramites = [
        tramite
        for tramite, distance in results
        if distance is not None and distance <= SEMANTIC_DISTANCE_THRESHOLD
    ]

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
            return process_consulta_semantica(db, pregunta)
        except Exception:
            return process_consulta_textual(pregunta, tramites)

    return process_consulta_textual(pregunta, tramites)
