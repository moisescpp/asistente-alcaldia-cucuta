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
    "Consulta por impuesto vehicular"
]

CLARIFICATION_SUGGESTIONS = [
    "Consulta por impuesto predial",
    "Consulta por impuesto vehicular",
    "Consulta por facilidades de pago",
    "Consulta por devolucion de pagos",
]

SEMANTIC_QUERY_LIMIT = 5
SEMANTIC_RESULT_LIMIT = 3
SEMANTIC_DISTANCE_THRESHOLD = 0.78
SEMANTIC_CONFIDENT_DISTANCE_THRESHOLD = 0.50
SEMANTIC_RELATED_DISTANCE_MARGIN = 0.08
SEMANTIC_MIN_DISTANCE_GAP = 0.03
GENERIC_QUERY_TOKENS = {
    "consulta",
    "consultar",
    "informacion",
    "informacion",
    "tramite",
    "tramites",
    "impuesto",
    "impuestos",
    "pagar",
    "pago",
    "pagos",
    "sobre",
    "necesito",
    "quiero",
    "ayuda",
    "algo",
    "como",
    "funciona",
    "funcionan",
    "saber",
    "tema",
    "tramitar",
    "publico",
    "publica",
    "servicio",
    "luz",
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

    fallback_intro = (
        f"El tramite principal para tu consulta es '{tramite_principal.nombre}'. "
        "A continuacion te comparto la informacion registrada en el sistema."
    )

    try:
        intro_text = generate_rag_response(
            pregunta=pregunta,
            tramites=tramites,
        )
    except Exception:
        intro_text = fallback_intro

    response_parts = [
        intro_text.strip(),
        "",
        f"Trámite principal: {tramite_principal.nombre}",
        "",
        "Datos registrados:",
        f"- Requisitos: {tramite_principal.requisitos or 'No hay informacion registrada en el sistema para este campo.'}",
        f"- Costo: {tramite_principal.costo or 'No hay informacion registrada en el sistema para este campo.'}",
        f"- Horario: {tramite_principal.horario or 'No hay informacion registrada en el sistema para este campo.'}",
        f"- Dependencia: {tramite_principal.dependencia}",
        f"- Fuente oficial: {tramite_principal.fuente_url or 'No hay informacion registrada en el sistema para este campo.'}",
    ]

    if related_matches:
        response_parts.extend(
            [
                "",
                "También pueden interesarte:",
                *[f"- {tramite.nombre}" for tramite in related_matches],
            ]
        )

    response_text = "\n".join(response_parts).strip()

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


def _build_clarification_response(pregunta: str) -> ConsultaResponse:
    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=(
            "La consulta es demasiado general para identificar un tramite con suficiente confianza. "
            "Especifica mejor el tema, por ejemplo el impuesto, servicio o gestion que necesitas."
        ),
        mensaje_estado="Consulta demasiado general",
        total_resultados=0,
        tramite_principal=None,
        tramites_relacionados=[],
        sugerencias=CLARIFICATION_SUGGESTIONS,
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


def _query_specific_tokens(pregunta: str) -> list[str]:
    normalized_question = _normalize_text(pregunta)
    tokens = [token for token in normalized_question.split() if len(token) > 2]
    return [token for token in tokens if token not in GENERIC_QUERY_TOKENS]


def _query_tokens(pregunta: str) -> list[str]:
    normalized_question = _normalize_text(pregunta)
    return [token for token in normalized_question.split() if len(token) > 2]


def _is_overly_generic_query(pregunta: str) -> bool:
    tokens = _query_tokens(pregunta)
    if not tokens:
        return True

    return len(tokens) == 1 and tokens[0] in GENERIC_QUERY_TOKENS


def _candidate_support(pregunta: str, tramite: Tramite) -> tuple[int, int, bool]:
    total_matches, specific_matches, phrase_match = _text_match_metadata(pregunta, tramite)
    support_rank = 2 if phrase_match else 1 if specific_matches > 0 else 0
    return support_rank, total_matches, phrase_match


def _select_semantic_candidates(
    pregunta: str,
    results: list[tuple[Tramite, float | None]],
) -> list[tuple[Tramite, float]]:
    if not results:
        return []

    tokens = _query_tokens(pregunta)
    specific_tokens = _query_specific_tokens(pregunta)
    ranked_results: list[tuple[Tramite, float, int, int, bool]] = []

    for tramite, distance in results:
        if distance is None:
            continue
        support_rank, total_matches, phrase_match = _candidate_support(pregunta, tramite)
        ranked_results.append(
            (tramite, distance, support_rank, total_matches, phrase_match),
        )

    if not ranked_results:
        return []

    supported_results = [
        item
        for item in ranked_results
        if item[2] > 0 and item[1] <= SEMANTIC_DISTANCE_THRESHOLD
    ]
    if supported_results:
        if not specific_tokens:
            supported_results = [
                item
                for item in supported_results
                if len(tokens) >= 2 and item[4]
            ]
            if not supported_results:
                return []
        supported_results.sort(
            key=lambda item: (
                item[2],
                item[3],
                1 if item[4] else 0,
                -item[1],
            ),
            reverse=True,
        )
        principal = supported_results[0]
        related_limit = min(
            SEMANTIC_DISTANCE_THRESHOLD,
            principal[1] + SEMANTIC_RELATED_DISTANCE_MARGIN,
        )
        selected = [
            (tramite, distance)
            for tramite, distance, support_rank, _, _ in supported_results
            if tramite.id == principal[0].id
            or (
                support_rank > 0
                and distance <= related_limit
            )
        ]
        return selected[:SEMANTIC_RESULT_LIMIT]

    best_tramite, best_distance, _, _, _ = min(
        ranked_results,
        key=lambda item: item[1],
    )
    second_distance = min(
        (
            item[1]
            for item in ranked_results
            if item[0].id != best_tramite.id
        ),
        default=None,
    )
    has_confident_gap = (
        second_distance is None
        or second_distance - best_distance >= SEMANTIC_MIN_DISTANCE_GAP
    )

    if specific_tokens and best_distance <= SEMANTIC_CONFIDENT_DISTANCE_THRESHOLD and has_confident_gap:
        return [(best_tramite, best_distance)]

    return []


def process_consulta_textual(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    tokens = _query_tokens(pregunta)
    generic_phrase_allowed = len(tokens) >= 2
    scored_tramites: list[tuple[Tramite, int, int, bool]] = []
    for tramite in tramites:
        if not tramite.activo:
            continue

        total_matches, specific_matches, phrase_match = _text_match_metadata(
            pregunta,
            tramite,
        )

        if total_matches > 0 and (
            specific_matches > 0 or (phrase_match and generic_phrase_allowed)
        ):
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

    filtered_results = _select_semantic_candidates(pregunta, results)
    filtered_tramites = [tramite for tramite, _ in filtered_results]

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
    if _is_overly_generic_query(pregunta):
        return _build_clarification_response(pregunta)

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
