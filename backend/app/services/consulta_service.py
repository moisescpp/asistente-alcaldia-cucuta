from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Tramite
from app.schemas.consulta import ConsultaMatch, ConsultaResponse
from app.services.embedding_service import generate_embedding, get_tramite_semantic_aliases
from app.services.rag_service import generate_rag_response


DEFAULT_SUGGESTIONS = [
    "Consulta por impuesto predial",
    "Consulta por generacion de paz y salvo",
    "Consulta por devolucion o compensacion de pagos",
    "Consulta por industria y comercio",
]

CLARIFICATION_SUGGESTIONS = [
    "Consulta por impuesto predial",
    "Consulta por generacion de paz y salvo",
    "Consulta por devolucion de pagos",
    "Consulta por industria y comercio",
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

INTENT_QUERY_TOKENS = {
    "cual",
    "cuales",
    "que",
    "cuanto",
    "cuanta",
    "cuesta",
    "coste",
    "donde",
    "cuando",
    "requisito",
    "requisitos",
    "costo",
    "costos",
    "horario",
    "horarios",
    "tramito",
    "tramita",
    "tramitar",
    "saco",
    "sacar",
    "renovar",
    "renovarlo",
    "duplicado",
    "hago",
    "hacen",
    "hacer",
    "alcaldia",
    "municipio",
    "para",
    "los",
    "las",
    "unos",
    "unas",
    "son",
    "del",
    "ante",
    "desde",
    "este",
    "esta",
    "estos",
    "estas",
    "permiso",
    "papeles",
    "documentos",
    "alcaldia",
    "con",
    "una",
    "uno",
    "unos",
    "unas",
    "del",
    "de",
    "al",
    "lo",
    "voy",
    "necesito",
    "quiero",
}

TECHNICAL_NOISE_TOKENS = {
    "test",
    "log",
}

OUT_OF_SCOPE_QUERY_TERMS = {
    "sisben",
    "vehicular",
    "transito",
    "movilidad",
    "licencia",
    "carro",
    "carros",
    "moto",
    "motos",
    "placa",
    "tarjeta de propiedad",
}


def _matches_token_group(token: str, token_group: set[str]) -> bool:
    return any(_is_fuzzy_token_match(token, candidate) for candidate in token_group)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).lower().strip()


def _tokenize_text(value: str | None) -> list[str]:
    normalized = _normalize_text(value)
    return [token for token in normalized.split() if len(token) > 2]


def _is_fuzzy_token_match(token: str, candidate: str) -> bool:
    if token == candidate:
        return True

    if min(len(token), len(candidate)) < 4:
        return False

    if token[0] != candidate[0]:
        return False

    return SequenceMatcher(None, token, candidate).ratio() >= 0.84


def _count_token_matches(tokens: list[str], searchable_words: set[str]) -> int:
    if not tokens or not searchable_words:
        return 0

    matches = 0
    for token in tokens:
        if any(_is_fuzzy_token_match(token, word) for word in searchable_words):
            matches += 1

    return matches


def _build_match(tramite: Tramite) -> ConsultaMatch:
    return ConsultaMatch(
        id=tramite.id,
        nombre=tramite.nombre,
        slug=tramite.slug,
        descripcion=tramite.descripcion,
        requisitos=tramite.requisitos,
        dirigido_a=tramite.dirigido_a,
        pasos=tramite.pasos,
        tiempo_estimado=tramite.tiempo_estimado,
        medio_seguimiento=tramite.medio_seguimiento,
        normatividad=tramite.normatividad,
        costo=tramite.costo,
        horario=tramite.horario,
        dependencia=tramite.dependencia,
        fuente_url=tramite.fuente_url,
        enlace_click_aqui=tramite.enlace_click_aqui,
    )


def _build_suggestion_label(tramite: Tramite) -> str:
    return f"Consulta por {tramite.nombre}"


def _build_searchable_text(tramite: Tramite) -> str:
    return " ".join(
        [
            _normalize_text(tramite.nombre),
            _normalize_text(tramite.descripcion),
            _normalize_text(tramite.requisitos),
            _normalize_text(tramite.dirigido_a),
            _normalize_text(tramite.pasos),
            _normalize_text(tramite.tiempo_estimado),
            _normalize_text(tramite.medio_seguimiento),
            _normalize_text(tramite.normatividad),
            _normalize_text(tramite.costo),
            _normalize_text(tramite.horario),
            _normalize_text(tramite.dependencia),
            _normalize_text(" ".join(get_tramite_semantic_aliases(tramite))),
        ]
    )


def _stable_catalog_order_key(pregunta: str, tramite: Tramite) -> str:
    reference = f"{_normalize_text(pregunta)}::{tramite.slug or tramite.nombre}"
    return hashlib.sha256(reference.encode("utf-8")).hexdigest()


def _build_no_match_suggestions(
    pregunta: str,
    tramites: list[Tramite],
) -> list[str]:
    active_tramites = [tramite for tramite in tramites if tramite.activo]
    if not active_tramites:
        return DEFAULT_SUGGESTIONS

    ranked_candidates: list[tuple[Tramite, int, int, int]] = []

    for tramite in active_tramites:
        total_matches, specific_matches, phrase_match = _text_match_metadata(
            pregunta,
            tramite,
        )
        identifier_specific_matches, identifier_phrase_match = _identifier_match_metadata(
            pregunta,
            tramite,
        )
        ranked_candidates.append(
            (
                tramite,
                max(specific_matches, identifier_specific_matches),
                total_matches,
                1 if phrase_match or identifier_phrase_match else 0,
            )
        )

    ranked_candidates.sort(
        key=lambda item: (
            item[1],
            item[2],
            item[3],
        ),
        reverse=True,
    )

    suggestions: list[str] = []
    seen: set[str] = set()

    for tramite, specific_matches, total_matches, phrase_match in ranked_candidates:
        if specific_matches == 0 and total_matches == 0 and phrase_match == 0:
            continue
        label = _build_suggestion_label(tramite)
        if label in seen:
            continue
        suggestions.append(label)
        seen.add(label)
        if len(suggestions) == 4:
            return suggestions

    remaining_tramites = sorted(
        active_tramites,
        key=lambda tramite: _stable_catalog_order_key(pregunta, tramite),
    )

    for tramite in remaining_tramites:
        label = _build_suggestion_label(tramite)
        if label in seen:
            continue
        suggestions.append(label)
        seen.add(label)
        if len(suggestions) == 4:
            break

    return suggestions or DEFAULT_SUGGESTIONS


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

    intro_text = fallback_intro
    if settings.enable_rag_intro:
        try:
            intro_text = generate_rag_response(
                pregunta=pregunta,
                tramites=tramites,
            )
        except Exception:
            intro_text = fallback_intro

    data_lines: list[str] = []
    missing_fields: list[str] = []

    if tramite_principal.descripcion:
        data_lines.append(f"- Descripcion: {tramite_principal.descripcion}")
    else:
        missing_fields.append("descripcion")

    if tramite_principal.requisitos:
        data_lines.append(f"- Requisitos: {tramite_principal.requisitos}")
    elif not tramite_principal.pasos:
        missing_fields.append("requisitos")

    if tramite_principal.dirigido_a:
        data_lines.append(f"- A quien va dirigido: {tramite_principal.dirigido_a}")

    if tramite_principal.pasos:
        data_lines.append(f"- Pasos para realizar el tramite: {tramite_principal.pasos}")

    if tramite_principal.tiempo_estimado:
        data_lines.append(f"- Tiempo estimado: {tramite_principal.tiempo_estimado}")

    if tramite_principal.medio_seguimiento:
        data_lines.append(f"- Medio para hacer seguimiento: {tramite_principal.medio_seguimiento}")

    if tramite_principal.normatividad:
        data_lines.append(f"- Normatividad: {tramite_principal.normatividad}")

    if tramite_principal.costo:
        data_lines.append(f"- Costo: {tramite_principal.costo}")
    else:
        missing_fields.append("costo")

    if tramite_principal.horario:
        data_lines.append(f"- Horario: {tramite_principal.horario}")
    else:
        missing_fields.append("horario")

    data_lines.append(f"- Dependencia: {tramite_principal.dependencia}")

    if tramite_principal.fuente_url:
        data_lines.append(f"- Fuente oficial: {tramite_principal.fuente_url}")
    else:
        missing_fields.append("fuente oficial")

    response_parts = [
        intro_text.strip(),
        "",
        f"Tramite principal: {tramite_principal.nombre}",
        "",
        "Datos registrados:",
        *data_lines,
    ]

    if missing_fields:
        response_parts.extend(
            [
                "",
                "Informacion pendiente en el sistema:",
                f"- {', '.join(missing_fields).capitalize()}.",
            ]
        )

    if related_matches:
        response_parts.extend(
            [
                "",
                "Tambien pueden interesarte:",
                *[f"- {tramite.nombre}" for tramite in related_matches],
            ]
        )

    follow_up_suggestions: list[str] = []
    if related_matches and len(_query_specific_tokens(pregunta)) <= 1:
        follow_up_suggestions = [
            f"Consulta por {tramite.nombre}" for tramite in related_matches[:3]
        ]

    response_text = "\n".join(response_parts).strip()

    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=response_text,
        mensaje_estado=message_status,
        total_resultados=len(tramites),
        tramite_principal=tramite_match,
        tramites_relacionados=related_matches,
        sugerencias=follow_up_suggestions,
    )


def _build_empty_response(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    suggestions = _build_no_match_suggestions(pregunta, tramites)
    example_text = ", ".join(suggestions[:3])
    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=(
            "No encontre un tramite directamente relacionado en la base actual. "
            "Esta version del asistente esta enfocada en rentas e impuestos; prueba con una consulta mas especifica o usa una de las sugerencias, por ejemplo: "
            f"{example_text}."
        ),
        mensaje_estado="Sin coincidencias en la base actual",
        total_resultados=0,
        tramite_principal=None,
        tramites_relacionados=[],
        sugerencias=suggestions,
    )


def _build_clarification_response(
    pregunta: str,
    candidate_tramites: list[Tramite] | None = None,
) -> ConsultaResponse:
    candidate_tramites = candidate_tramites or []
    candidate_matches = [_build_match(tramite) for tramite in candidate_tramites[:3]]
    candidate_suggestions = [f"Consulta por {tramite.nombre}" for tramite in candidate_tramites[:3]]
    suggestions = candidate_suggestions or CLARIFICATION_SUGGESTIONS
    example_text = ", ".join(suggestions[:3])
    response_text = (
        "La consulta es demasiado general para identificar un tramite con suficiente confianza. "
        "Especifica mejor el tema, por ejemplo el impuesto, servicio o gestion que necesitas. "
        f"Puedes intentar con algo como: {example_text}."
    )

    if candidate_matches:
        response_text = (
            "La consulta puede corresponder a varios tramites posibles dentro de rentas e impuestos. "
            "Te recomiendo elegir una de las opciones sugeridas para responderte con mas precision."
        )

    return ConsultaResponse(
        pregunta=pregunta,
        respuesta=response_text,
        mensaje_estado="Consulta demasiado general",
        total_resultados=len(candidate_matches),
        tramite_principal=None,
        tramites_relacionados=candidate_matches,
        sugerencias=suggestions,
    )


def _text_match_metadata(pregunta: str, tramite: Tramite) -> tuple[int, int, bool]:
    normalized_question = _normalize_text(pregunta)
    tokens = _query_tokens(pregunta)
    specific_tokens = _query_specific_tokens(pregunta)
    searchable_text = _build_searchable_text(tramite)
    searchable_words = set(_tokenize_text(searchable_text))

    total_matches = _count_token_matches(tokens, searchable_words)
    specific_matches = _count_token_matches(specific_tokens, searchable_words)
    phrase_match = len(normalized_question) >= 5 and normalized_question in searchable_text

    return total_matches, specific_matches, phrase_match


def _identifier_match_metadata(pregunta: str, tramite: Tramite) -> tuple[int, bool]:
    normalized_question = _normalize_text(pregunta)
    specific_tokens = _query_specific_tokens(pregunta)
    normalized_aliases = [
        _normalize_text(alias)
        for alias in _high_confidence_aliases(tramite)
        if len(_normalize_text(alias).split()) >= 2
    ]

    identifier_text = " ".join(
        [
            _normalize_text(tramite.nombre),
            _normalize_text(tramite.slug),
            _normalize_text(" ".join(_high_confidence_aliases(tramite))),
        ]
    )
    identifier_words = set(_tokenize_text(identifier_text))

    specific_matches = _count_token_matches(specific_tokens, identifier_words)
    phrase_match = len(normalized_question) >= 5 and (
        normalized_question in identifier_text
        or any(alias in normalized_question for alias in normalized_aliases)
    )

    return specific_matches, phrase_match


def _high_confidence_aliases(tramite: Tramite) -> list[str]:
    searchable_text = _normalize_text(
        " ".join([tramite.nombre or "", tramite.slug or ""]),
    )

    if "cancelacion" in searchable_text and "contribuyentes" in searchable_text:
        return [
            "cancelar registro",
            "cerrar registro",
            "cerrar negocio",
            "cierre de negocio",
            "cese de actividades",
            "retirar industria y comercio",
            "cancelar industria y comercio",
            "ya no tengo negocio",
            "dejar de pagar industria y comercio",
        ]

    if "sisben" in searchable_text:
        return [
            "sisben",
            "actualizar sisben",
            "actualizar el sisben",
            "cambiar datos del sisben",
            "cambiar el sisben",
            "cambio de direccion sisben",
            "cambio de domicilio sisben",
            "actualizar datos",
            "encuesta sisben",
        ]

    if "predial" in searchable_text:
        return [
            "casa",
            "vivienda",
            "predio",
            "inmueble",
            "terreno",
            "catastro",
            "ficha catastral",
            "recibo predial",
            "lo de la casa",
            "impuesto de casa",
            "impuesto de vivienda",
            "impuesto de predio",
        ]

    if (
        "registro" in searchable_text
        and "contribuyentes" in searchable_text
        and "modificacion" not in searchable_text
        and "cancelacion" not in searchable_text
    ):
        return [
            "registrar negocio",
            "abrir negocio",
            "inscribir negocio",
            "inscribir industria y comercio",
            "registro de negocio",
            "registro de comercio",
            "registro ica",
            "matricula de negocio",
            "nuevo negocio",
        ]

    if "modificacion" in searchable_text and "contribuyentes" in searchable_text:
        return [
            "modificar registro",
            "actualizar registro",
            "cambiar datos",
            "actualizar datos del negocio",
            "cambio de direccion",
            "cambio de propietario",
            "cambio de actividad",
            "modificar industria y comercio",
        ]

    if "industria" in searchable_text and "comercio" in searchable_text:
        return [
            "industria y comercio",
            "impuesto de industria y comercio",
            "declaracion de industria y comercio",
        ]

    if "espectaculos" in searchable_text:
        return [
            "concierto",
            "evento",
            "evento publico",
            "evento masivo",
            "fiesta",
            "baile",
            "orquesta",
            "presentacion musical",
            "show",
            "boletas",
            "boleteria",
            "hacer un evento",
            "evento con entrada",
        ]

    if "alumbrado" in searchable_text:
        return [
            "alumbrado publico",
            "servicio de alumbrado",
            "impuesto de alumbrado",
            "iluminacion publica",
            "luz publica",
            "recibo de luz",
            "servicio de la luz",
            "lo de la luz",
        ]

    if "devolucion" in searchable_text or "compensacion" in searchable_text:
        return [
            "devolver dinero",
            "devolver plata",
            "reembolso",
            "reintegro",
            "pago en exceso",
            "pago por error",
            "pague de mas",
            "me cobraron de mas",
            "saldo a favor",
            "compensar saldo",
            "devolucion de pago",
        ]

    if "paz" in searchable_text and "salvo" in searchable_text:
        return [
            "paz y salvo",
            "certificado paz y salvo",
            "estar al dia",
            "certificado de impuestos",
            "paz y salbo",
            "certificado de deuda",
            "debo impuestos",
            "sacar paz y salvo",
        ]

    if "licencia" in searchable_text and "transito" in searchable_text:
        return [
            "duplicado licencia",
            "duplicado de licencia de transito",
            "tarjeta de propiedad",
            "se me perdio la licencia",
            "se me perdio la tarjeta del carro",
            "papeles del carro",
            "copia licencia de transito",
        ]

    return []


def _contains_any_phrase(normalized_question: str, phrases: list[str]) -> bool:
    return any(_normalize_text(phrase) in normalized_question for phrase in phrases)


def _find_active_tramite_by_name(
    tramites: list[Tramite],
    *,
    required_terms: list[str],
    excluded_terms: list[str] | None = None,
) -> Tramite | None:
    excluded_terms = excluded_terms or []

    for tramite in tramites:
        if not tramite.activo:
            continue

        searchable_text = _normalize_text(" ".join([tramite.nombre or "", tramite.slug or ""]))
        if all(term in searchable_text for term in required_terms) and not any(
            term in searchable_text for term in excluded_terms
        ):
            return tramite

    return None


def _build_direct_intent_response(
    pregunta: str,
    principal: Tramite,
    tramites: list[Tramite],
) -> ConsultaResponse:
    related = [
        tramite
        for tramite in tramites
        if tramite.activo and tramite.id != principal.id
    ]
    return _build_success_response(
        pregunta=pregunta,
        tramites=[principal, *related[: SEMANTIC_RESULT_LIMIT - 1]],
        message_status="Coincidencias encontradas",
    )


def _detect_direct_citizen_intent(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse | None:
    normalized_question = _normalize_text(pregunta)

    intent_rules = [
        (
            [
                "cerrar negocio",
                "cierre de negocio",
                "cancelar industria y comercio",
                "cancelar registro",
                "cese de actividades",
                "dar de baja",
                "ya no tengo negocio",
                "retirar industria y comercio",
            ],
            {
                "required_terms": ["cancelacion", "registro", "contribuyentes"],
            },
        ),
        (
            [
                "corregir declaracion",
                "correccion de declaracion",
                "correccion de año",
                "periodo gravable",
                "error en declaracion",
                "errores en declaracion",
                "inconsistencia en declaracion",
                "declaracion de industria y comercio",
            ],
            {
                "required_terms": ["correccion", "industria", "comercio"],
            },
        ),
        (
            [
                "abrir negocio",
                "abrir un negocio",
                "registrar negocio",
                "registrar mi negocio",
                "registrar comercio",
                "registrar mi comercio",
                "inscribir negocio",
                "inscribir mi negocio",
                "inscribir industria y comercio",
                "inscribir actividad comercial",
                "inscribo mi actividad comercial",
                "registro ica",
                "sacar registro ica",
                "matricula de negocio",
                "legalizar mi negocio",
                "abrir local",
                "registrarme como contribuyente",
            ],
            {
                "required_terms": ["registro", "contribuyentes"],
                "excluded_terms": ["cancelacion", "modificacion", "correccion"],
            },
        ),
        (
            [
                "sisben",
                "actualizar sisben",
                "actualizar el sisben",
                "cambiar datos del sisben",
                "cambio de direccion sisben",
                "cambio de domicilio sisben",
                "encuesta sisben",
            ],
            {
                "required_terms": ["sisben"],
            },
        ),
        (
            [
                "cambiar datos",
                "cambio de direccion",
                "actualizar datos del negocio",
                "actualizar industria y comercio",
                "modificar industria y comercio",
                "cambio de actividad",
                "cambiar actividad",
            ],
            {
                "required_terms": ["modificacion", "registro", "contribuyentes"],
            },
        ),
        (
            [
                "actividad con publico",
                "actividad con público",
                "evento con publico",
                "evento publico",
                "espectaculo publico",
                "espectaculos publicos",
                "concierto",
                "boletas",
                "boleteria",
                "fiesta con entrada",
                "orquesta",
                "show",
                "presentacion musical",
            ],
            {
                "required_terms": ["espectaculos"],
            },
        ),
        (
            [
                "deudas con la alcaldia",
                "deuda con la alcaldia",
                "si tengo deudas",
                "saber si tengo deudas",
                "estoy al dia",
                "no debo impuestos",
                "certificado de deuda",
                "certificado de impuestos",
                "certificado para vender casa",
                "certificado para vender una casa",
                "vender casa",
                "vender una casa",
                "constancia de no deuda",
                "paz y salvo",
                "paz y salbo",
            ],
            {
                "required_terms": ["paz", "salvo"],
            },
        ),
    ]

    for phrases, target in intent_rules:
        if not _contains_any_phrase(normalized_question, phrases):
            continue

        principal = _find_active_tramite_by_name(tramites, **target)
        if principal is not None:
            return _build_direct_intent_response(pregunta, principal, tramites)

    return None


def _query_specific_tokens(pregunta: str) -> list[str]:
    normalized_question = _normalize_text(pregunta)
    tokens = [token for token in normalized_question.split() if len(token) > 2]
    return [
        token
        for token in tokens
        if not _matches_token_group(token, GENERIC_QUERY_TOKENS)
        and not _matches_token_group(token, INTENT_QUERY_TOKENS)
    ]


def _query_tokens(pregunta: str) -> list[str]:
    normalized_question = _normalize_text(pregunta)
    return [token for token in normalized_question.split() if len(token) > 2]


def _query_domain_tokens(pregunta: str) -> list[str]:
    return [
        token
        for token in _query_tokens(pregunta)
        if not _matches_token_group(token, INTENT_QUERY_TOKENS)
        and token not in TECHNICAL_NOISE_TOKENS
    ]


def _domain_match_count(pregunta: str, tramite: Tramite) -> int:
    domain_tokens = _query_domain_tokens(pregunta)
    searchable_text = " ".join(
        [
            _normalize_text(tramite.nombre),
            _normalize_text(tramite.descripcion),
            _normalize_text(tramite.requisitos),
            _normalize_text(tramite.dirigido_a),
            _normalize_text(tramite.pasos),
            _normalize_text(tramite.normatividad),
            _normalize_text(" ".join(get_tramite_semantic_aliases(tramite))),
        ]
    )
    searchable_words = set(_tokenize_text(searchable_text))
    return _count_token_matches(domain_tokens, searchable_words)


def _is_overly_generic_query(pregunta: str) -> bool:
    tokens = _query_tokens(pregunta)
    if not tokens:
        return True

    specific_tokens = _query_specific_tokens(pregunta)
    if not specific_tokens:
        return True

    return len(tokens) == 1 and (
        _matches_token_group(tokens[0], GENERIC_QUERY_TOKENS)
        or _matches_token_group(tokens[0], INTENT_QUERY_TOKENS)
    )


def _references_out_of_scope_topic(pregunta: str) -> bool:
    normalized_question = _normalize_text(pregunta)
    return any(term in normalized_question for term in OUT_OF_SCOPE_QUERY_TERMS)


def _candidate_support(pregunta: str, tramite: Tramite) -> tuple[int, int, bool, int, int, bool]:
    total_matches, specific_matches, phrase_match = _text_match_metadata(pregunta, tramite)
    identifier_specific_matches, identifier_phrase_match = _identifier_match_metadata(
        pregunta,
        tramite,
    )
    support_rank = 2 if identifier_phrase_match else 1 if identifier_specific_matches > 0 else 0
    return (
        support_rank,
        identifier_specific_matches,
        identifier_phrase_match,
        specific_matches,
        total_matches,
        phrase_match,
    )


def _deduplicate_tramites(tramites: list[Tramite]) -> list[Tramite]:
    unique_tramites: list[Tramite] = []
    seen_ids: set[int] = set()

    for tramite in tramites:
        if tramite.id in seen_ids:
            continue
        seen_ids.add(tramite.id)
        unique_tramites.append(tramite)

    return unique_tramites


def _find_tramite_by_id(tramites: list[Tramite], tramite_id: int | None) -> Tramite | None:
    if tramite_id is None:
        return None

    for tramite in tramites:
        if tramite.id == tramite_id:
            return tramite

    return None


def _should_prefer_textual_response(
    pregunta: str,
    *,
    semantic_response: ConsultaResponse,
    textual_response: ConsultaResponse,
    tramites: list[Tramite],
) -> bool:
    semantic_principal = _find_tramite_by_id(
        tramites,
        semantic_response.tramite_principal.id if semantic_response.tramite_principal else None,
    )
    textual_principal = _find_tramite_by_id(
        tramites,
        textual_response.tramite_principal.id if textual_response.tramite_principal else None,
    )

    if semantic_principal is None or textual_principal is None:
        return False

    semantic_support = _candidate_support(pregunta, semantic_principal)
    textual_support = _candidate_support(pregunta, textual_principal)

    return textual_support > semantic_support


def _is_textual_fast_path_confident(
    pregunta: str,
    textual_response: ConsultaResponse,
    tramites: list[Tramite],
) -> bool:
    if textual_response.total_resultados <= 0 or textual_response.tramite_principal is None:
        return False

    textual_principal = _find_tramite_by_id(
        tramites,
        textual_response.tramite_principal.id,
    )
    if textual_principal is None:
        return False

    (
        support_rank,
        identifier_specific_matches,
        identifier_phrase_match,
        specific_matches,
        _total_matches,
        phrase_match,
    ) = _candidate_support(pregunta, textual_principal)

    specific_tokens = [
        token
        for token in _query_specific_tokens(pregunta)
        if token not in TECHNICAL_NOISE_TOKENS
    ]
    if not specific_tokens:
        return False

    identifier_text = " ".join(
        [
            _normalize_text(textual_principal.nombre),
            _normalize_text(textual_principal.slug),
            _normalize_text(" ".join(_high_confidence_aliases(textual_principal))),
        ]
    )
    identifier_words = set(_tokenize_text(identifier_text))
    has_strong_identifier_token = any(
        any(_is_fuzzy_token_match(token, word) for word in identifier_words)
        for token in specific_tokens
    )

    return (
        identifier_phrase_match
        or (support_rank > 0 and has_strong_identifier_token)
        or (identifier_specific_matches >= 1 and has_strong_identifier_token)
        or specific_matches >= 2
        or (specific_matches >= 1 and phrase_match)
    )


def _find_clarification_candidates(
    db: Session,
    pregunta: str,
    tramites: list[Tramite],
) -> list[Tramite]:
    specific_tokens = _query_specific_tokens(pregunta)
    textual_candidates: list[tuple[Tramite, int, int, bool]] = []
    for tramite in tramites:
        if not tramite.activo:
            continue

        total_matches, specific_matches, phrase_match = _text_match_metadata(
            pregunta,
            tramite,
        )
        identifier_specific_matches, identifier_phrase_match = _identifier_match_metadata(
            pregunta,
            tramite,
        )
        domain_matches = _domain_match_count(pregunta, tramite)

        if not specific_tokens and domain_matches == 0 and not identifier_phrase_match:
            continue

        if total_matches > 0 or identifier_specific_matches > 0 or identifier_phrase_match:
            textual_candidates.append(
                (
                    tramite,
                    max(
                        specific_matches,
                        identifier_specific_matches,
                        domain_matches if not specific_tokens else 0,
                    ),
                    domain_matches if not specific_tokens else total_matches,
                    phrase_match or identifier_phrase_match,
                )
            )

    textual_candidates.sort(
        key=lambda item: (
            item[1],
            item[2],
            1 if item[3] else 0,
        ),
        reverse=True,
    )
    candidate_tramites = [tramite for tramite, _, _, _ in textual_candidates[:3]]
    candidate_tramites = _deduplicate_tramites(candidate_tramites)

    if len(candidate_tramites) >= SEMANTIC_RESULT_LIMIT or not specific_tokens:
        return candidate_tramites[:3]

    try:
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
        semantic_results = db.execute(query).all()
        candidate_tramites.extend(
            tramite
            for tramite, distance in semantic_results
            if distance is not None and distance <= min(0.9, SEMANTIC_DISTANCE_THRESHOLD + 0.12)
        )
    except Exception:
        pass

    return _deduplicate_tramites(candidate_tramites)[:3]


def _select_semantic_candidates(
    pregunta: str,
    results: list[tuple[Tramite, float | None]],
) -> list[tuple[Tramite, float]]:
    if not results:
        return []

    tokens = _query_tokens(pregunta)
    specific_tokens = _query_specific_tokens(pregunta)
    ranked_results: list[tuple[Tramite, float, int, int, bool, int, int, bool]] = []

    for tramite, distance in results:
        if distance is None:
            continue
        (
            support_rank,
            identifier_specific_matches,
            identifier_phrase_match,
            specific_matches,
            total_matches,
            phrase_match,
        ) = _candidate_support(
            pregunta,
            tramite,
        )
        ranked_results.append(
            (
                tramite,
                distance,
                support_rank,
                identifier_specific_matches,
                identifier_phrase_match,
                specific_matches,
                total_matches,
                phrase_match,
            )
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
                item[5],
                item[6],
                1 if item[7] else 0,
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
            for tramite, distance, support_rank, _, _, _, _, _ in supported_results
            if tramite.id == principal[0].id
            or (support_rank > 0 and distance <= related_limit)
        ]
        return selected[:SEMANTIC_RESULT_LIMIT]

    return []


def process_consulta_textual(
    pregunta: str,
    tramites: list[Tramite],
) -> ConsultaResponse:
    tokens = _query_tokens(pregunta)
    generic_phrase_allowed = len(tokens) >= 2
    specific_tokens = _query_specific_tokens(pregunta)
    scored_tramites: list[tuple[Tramite, int, int, int, int, bool]] = []

    for tramite in tramites:
        if not tramite.activo:
            continue

        total_matches, specific_matches, phrase_match = _text_match_metadata(
            pregunta,
            tramite,
        )
        identifier_specific_matches, identifier_phrase_match = _identifier_match_metadata(
            pregunta,
            tramite,
        )

        has_identifier_support = (
            identifier_specific_matches > 0 or identifier_phrase_match
        )
        identifier_rank = 2 if identifier_phrase_match else 1 if identifier_specific_matches > 0 else 0
        has_registered_content_support = (
            specific_matches >= 2 or (specific_matches >= 1 and phrase_match)
        )

        if total_matches > 0 and (
            has_identifier_support
            or has_registered_content_support
            or (
                not specific_tokens
                and phrase_match
                and generic_phrase_allowed
            )
        ):
            scored_tramites.append(
                (
                    tramite,
                    identifier_rank,
                    identifier_specific_matches,
                    max(specific_matches, identifier_specific_matches),
                    total_matches,
                    phrase_match or identifier_phrase_match,
                )
            )

    matched_tramites = [tramite for tramite, _, _, _, _, _ in scored_tramites]
    matched_tramites.sort(
        key=lambda candidate: next(
            (
                (
                    identifier_rank,
                    identifier_specific_matches,
                    specific_matches,
                    total_matches,
                    1 if phrase_match else 0,
                )
                for (
                    tramite,
                    identifier_rank,
                    identifier_specific_matches,
                    specific_matches,
                    total_matches,
                    phrase_match,
                ) in scored_tramites
                if tramite.id == candidate.id
            ),
            (0, 0, 0, 0, 0),
        ),
        reverse=True,
    )

    if not matched_tramites:
        return _build_empty_response(pregunta, tramites)

    return _build_success_response(
        pregunta=pregunta,
        tramites=matched_tramites[:SEMANTIC_RESULT_LIMIT],
        message_status="Coincidencias encontradas",
    )


def process_consulta_semantica(
    db: Session,
    pregunta: str,
    tramites: list[Tramite],
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
        return _build_empty_response(pregunta, tramites)

    filtered_results = _select_semantic_candidates(pregunta, results)
    filtered_tramites = [tramite for tramite, _ in filtered_results]

    if not filtered_tramites:
        return _build_empty_response(pregunta, tramites)

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
    if _references_out_of_scope_topic(pregunta):
        return _build_empty_response(pregunta, tramites)

    direct_intent_response = _detect_direct_citizen_intent(pregunta, tramites)
    if direct_intent_response is not None:
        return direct_intent_response

    if _is_overly_generic_query(pregunta) and not _has_registered_phrase_support(
        pregunta,
        tramites,
    ):
        clarification_candidates = _find_clarification_candidates(db, pregunta, tramites)
        return _build_clarification_response(pregunta, clarification_candidates)

    textual_response = process_consulta_textual(pregunta, tramites)
    has_semantic_data = any(
        tramite.activo and tramite.embedding_vector is not None for tramite in tramites
    )

    if has_semantic_data:
        if _is_textual_fast_path_confident(pregunta, textual_response, tramites):
            return textual_response

        try:
            semantic_response = process_consulta_semantica(db, pregunta, tramites)

            if semantic_response.total_resultados > 0 and textual_response.total_resultados > 0:
                if _should_prefer_textual_response(
                    pregunta,
                    semantic_response=semantic_response,
                    textual_response=textual_response,
                    tramites=tramites,
                ):
                    return textual_response
                return semantic_response

            if semantic_response.total_resultados > 0:
                return semantic_response

            if textual_response.total_resultados > 0:
                return textual_response

            return semantic_response
        except Exception:
            return textual_response

    return textual_response


def _has_registered_phrase_support(pregunta: str, tramites: list[Tramite]) -> bool:
    normalized_question = _normalize_text(pregunta)
    if len(normalized_question) < 5 or len(_query_tokens(pregunta)) < 2:
        return False

    return any(
        tramite.activo and (
            _text_match_metadata(pregunta, tramite)[2]
            or _identifier_match_metadata(pregunta, tramite)[1]
        )
        for tramite in tramites
    )
