from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Tramite


def _normalize(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


def _split_alias_text(value: str | None) -> list[str]:
    if not value:
        return []

    raw_aliases = value.replace("\r", "\n").replace(";", ",").splitlines()
    aliases: list[str] = []

    for chunk in raw_aliases:
        for item in chunk.split(","):
            normalized = item.strip()
            if normalized:
                aliases.append(normalized)

    return aliases


def _deduplicate_aliases(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}

    for value in values:
        normalized = _clean_phrase(value)
        if normalized:
            seen.setdefault(normalized, None)

    return list(seen.keys())


INTENT_ALIAS_GROUPS: list[tuple[set[str], list[str]]] = [
    (
        {
            "modificacion",
            "modificar",
            "actualizacion",
            "actualizar",
            "cambio",
            "cambios",
            "ajuste",
            "ajustes",
            "edicion",
            "editar",
            "correccion",
            "corregir",
        },
        [
            "cambio",
            "cambios",
            "modificar",
            "modificacion",
            "actualizar",
            "actualizacion",
            "editar",
            "edicion",
            "corregir",
            "correccion",
        ],
    ),
    (
        {"registro", "registrar", "inscripcion", "inscribir"},
        [
            "registro",
            "registrar",
            "inscripcion",
            "inscribir",
        ],
    ),
    (
        {"cancelacion", "cancelar", "retiro", "baja", "eliminar"},
        [
            "cancelar",
            "cancelacion",
            "retiro",
            "dar de baja",
            "eliminar registro",
        ],
    ),
    (
        {"certificado", "certificacion", "certificar", "constancia"},
        [
            "certificado",
            "certificacion",
            "constancia",
            "soporte",
        ],
    ),
    (
        {"liquidacion", "liquidar"},
        [
            "liquidacion",
            "liquidar",
            "calcular",
        ],
    ),
]

TOPIC_STOPWORDS = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "para",
    "por",
    "con",
    "sin",
    "ante",
    "sobre",
    "desde",
    "hacia",
    "entre",
    "mediante",
    "tramite",
    "tramites",
    "proceso",
    "gestion",
    "servicio",
}


def _tokenize_normalized_text(value: str | None) -> set[str]:
    normalized = _normalize(value)
    return {token for token in re.split(r"[^a-z0-9]+", normalized) if token}


def _ordered_tokens(value: str | None) -> list[str]:
    normalized = _normalize(value)
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token]


def _clean_phrase(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"\s+", " ", _normalize(value)).strip(" -,:;")


def _extract_phrase_candidates(tramite: Tramite) -> list[str]:
    raw_name = tramite.nombre or ""
    fragments = re.split(r"[\u2013\u2014\-:/|]+", raw_name)
    candidates: list[str] = []

    for fragment in fragments:
        cleaned = _clean_phrase(fragment)
        if cleaned and len(cleaned.split()) >= 2:
            candidates.append(cleaned)

    full_name = _clean_phrase(raw_name)
    if full_name:
        candidates.append(full_name)

    seen: dict[str, None] = {}
    for candidate in candidates:
        seen.setdefault(candidate, None)

    return list(seen.keys())[:4]


def _extract_context_chunks(value: str | None, *, max_items: int = 4) -> list[str]:
    if not value:
        return []

    raw_fragments = re.split(r"[\n,;:.]+", value)
    chunks: list[str] = []

    for fragment in raw_fragments:
        cleaned = _clean_phrase(fragment)
        if not cleaned:
            continue

        tokens = [token for token in cleaned.split() if token not in TOPIC_STOPWORDS]
        if len(tokens) < 2:
            continue

        chunks.append(" ".join(tokens[:4]))
        if len(chunks) == max_items:
            break

    return chunks


def _extract_significant_bigrams(value: str | None, *, max_items: int = 4) -> list[str]:
    tokens = [
        token
        for token in _ordered_tokens(value)
        if token not in TOPIC_STOPWORDS
    ]
    bigrams: list[str] = []

    for index in range(len(tokens) - 1):
        bigrams.append(f"{tokens[index]} {tokens[index + 1]}")
        if len(bigrams) == max_items:
            break

    return bigrams


def _strip_intent_prefix(phrase: str) -> str:
    if not phrase:
        return ""

    tokens = [token for token in phrase.split() if token]
    while tokens and any(tokens[0] in trigger_tokens for trigger_tokens, _ in INTENT_ALIAS_GROUPS):
        tokens.pop(0)

    while tokens and tokens[0] in TOPIC_STOPWORDS:
        tokens.pop(0)

    return " ".join(tokens).strip()


def _simplify_topic_phrase(phrase: str) -> str:
    tokens = [token for token in phrase.split() if token]
    filtered_tokens = [token for token in tokens if token not in TOPIC_STOPWORDS]

    if len(filtered_tokens) >= 2:
        return " ".join(filtered_tokens)

    return phrase


def _extract_topic_phrases(tramite: Tramite) -> list[str]:
    candidates = _extract_phrase_candidates(tramite)
    topic_candidates: list[str] = []

    for candidate in candidates:
        cleaned_candidate = _clean_phrase(candidate)
        if cleaned_candidate:
            topic_candidates.append(cleaned_candidate)

        stripped_candidate = _strip_intent_prefix(cleaned_candidate)
        if stripped_candidate and len(stripped_candidate.split()) >= 2:
            topic_candidates.append(stripped_candidate)

        simplified_candidate = _simplify_topic_phrase(stripped_candidate or cleaned_candidate)
        if simplified_candidate and len(simplified_candidate.split()) >= 2:
            topic_candidates.append(simplified_candidate)

    topic_candidates.extend(_extract_significant_bigrams(tramite.descripcion, max_items=4))
    topic_candidates.extend(_extract_significant_bigrams(tramite.requisitos, max_items=4))
    topic_candidates.extend(_extract_significant_bigrams(tramite.pasos, max_items=4))
    topic_candidates.extend(_extract_significant_bigrams(tramite.dirigido_a, max_items=3))
    topic_candidates.extend(_extract_context_chunks(tramite.descripcion, max_items=3))
    topic_candidates.extend(_extract_context_chunks(tramite.requisitos, max_items=4))
    topic_candidates.extend(_extract_context_chunks(tramite.pasos, max_items=4))
    topic_candidates.extend(_extract_context_chunks(tramite.medio_seguimiento, max_items=3))
    topic_candidates.extend(_extract_context_chunks(tramite.normatividad, max_items=3))
    topic_candidates.extend(_extract_context_chunks(tramite.dependencia, max_items=2))

    seen: dict[str, None] = {}
    for candidate in topic_candidates:
        cleaned_candidate = _clean_phrase(candidate)
        if cleaned_candidate and len(cleaned_candidate.split()) >= 2:
            seen.setdefault(cleaned_candidate, None)

    return list(seen.keys())[:10]


def _build_intent_topic_aliases(expansions: list[str], topic_phrases: list[str]) -> list[str]:
    aliases: list[str] = []

    for topic in topic_phrases:
        for alias in expansions[:5]:
            aliases.append(f"{alias} {topic}")
            aliases.append(f"{alias} de {topic}")
            aliases.append(f"{alias} en {topic}")
            aliases.append(f"hacer {alias} en {topic}")

    return aliases


GENERIC_ALIAS_PREFIXES = (
    "informacion sobre ",
    "consulta sobre ",
    "tramite de ",
    "requisitos para ",
    "papeles para ",
    "documentos para ",
    "como hago ",
    "hacer ",
    "pagar ",
    "donde se paga ",
)


def _filter_generated_aliases(tramite: Tramite, aliases: list[str]) -> list[str]:
    source_tokens = _tokenize_normalized_text(
        " ".join(
            [
                tramite.nombre or "",
                tramite.slug or "",
                tramite.descripcion or "",
                tramite.requisitos or "",
                tramite.dirigido_a or "",
                tramite.pasos or "",
                tramite.medio_seguimiento or "",
                tramite.normatividad or "",
                tramite.enlace_click_aqui or "",
                tramite.dependencia or "",
            ]
        )
    )
    filtered_aliases: list[str] = []

    for alias in aliases:
        normalized_alias = _clean_phrase(alias)
        if not normalized_alias:
            continue

        if any(char.isdigit() for char in normalized_alias):
            continue

        if normalized_alias.startswith(GENERIC_ALIAS_PREFIXES):
            continue

        alias_tokens = _tokenize_normalized_text(normalized_alias)
        if not alias_tokens or len(alias_tokens) > 8:
            continue

        if source_tokens and not alias_tokens.intersection(source_tokens):
            continue

        filtered_aliases.append(normalized_alias)

    return filtered_aliases


def _infer_intent_aliases(tramite: Tramite) -> list[str]:
    searchable_tokens = _tokenize_normalized_text(
        " ".join(
            [
                tramite.nombre or "",
                tramite.slug or "",
                tramite.descripcion or "",
                tramite.requisitos or "",
                tramite.dirigido_a or "",
                tramite.pasos or "",
                tramite.medio_seguimiento or "",
                tramite.normatividad or "",
                tramite.enlace_click_aqui or "",
                tramite.dependencia or "",
            ]
        )
    )
    topic_phrases = _extract_topic_phrases(tramite)
    aliases: list[str] = []

    for trigger_tokens, expansions in INTENT_ALIAS_GROUPS:
        if searchable_tokens.intersection(trigger_tokens):
            aliases.extend(expansions)
            aliases.extend(_build_intent_topic_aliases(expansions, topic_phrases))

    aliases.extend(topic_phrases)

    return aliases


def _get_domain_rule_aliases(tramite: Tramite) -> list[str]:
    searchable_text = _normalize(
        " ".join(
            [
                tramite.nombre or "",
                tramite.slug or "",
                tramite.descripcion or "",
                tramite.dirigido_a or "",
                tramite.pasos or "",
            ]
        )
    )

    if "espectaculos" in searchable_text:
        return [
            "concierto",
            "conciertos",
            "evento",
            "eventos",
            "evento masivo",
            "eventos masivos",
            "evento publico",
            "eventos publicos",
            "festival",
            "show",
            "tarima",
            "baile",
            "baile publico",
            "orquesta",
            "evento musical",
            "presentacion musical",
            "presentacion publica",
            "fiesta",
            "fiesta publica",
            "hacer un concierto",
            "hacer concierto",
            "hacer una fiesta",
            "papeles para concierto",
            "papeles para hacer un concierto",
            "documentos para concierto",
            "requisitos para concierto",
            "impuesto para concierto",
            "boletas",
            "taquilla",
            "impuesto para conciertos",
            "impuesto para eventos",
            "impuesto para eventos masivos",
        ]

    return []


def _build_alias_generation_prompt(tramite: Tramite) -> str:
    return (
        "Genera entre 6 y 10 formas cortas y naturales en las que la ciudadania podria "
        "preguntar por este tramite. Incluye lenguaje cotidiano, intencion y contexto. "
        "Devuelve solo JSON valido con una clave 'aliases' que contenga una lista de strings, sin explicaciones.\n\n"
        f"Nombre: {tramite.nombre}\n"
        f"Descripcion: {tramite.descripcion or 'Sin descripcion registrada'}\n"
        f"A quien va dirigido: {tramite.dirigido_a or 'Sin destinatario registrado'}\n"
        f"Pasos: {tramite.pasos or tramite.requisitos or 'Sin pasos registrados'}\n"
        f"Dependencia: {tramite.dependencia}\n"
    )


def _extract_aliases_from_response(data: dict[str, Any]) -> list[str]:
    output_items = data.get("output", [])
    text_fragments: list[str] = []

    for item in output_items:
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                text_fragments.append(content["text"].strip())

    if not text_fragments:
        return []

    raw_text = "\n".join(text_fragments).strip()

    try:
        parsed = json.loads(raw_text)
        aliases = parsed.get("aliases", [])
        if isinstance(aliases, list):
            return [str(alias).strip() for alias in aliases if str(alias).strip()]
    except Exception:
        pass

    return []


def generate_citizen_aliases(tramite: Tramite) -> list[str]:
    if not settings.openai_api_key:
        return []

    payload: dict[str, Any] = {
        "model": settings.response_model,
        "instructions": (
            "Eres un asistente de lenguaje ciudadano para tramites tributarios de una alcaldia. "
            "Tu tarea es traducir nombres formales de tramites a formas naturales en que preguntaria la ciudadania. "
            "No inventes tramites distintos ni temas no relacionados. No des explicaciones. "
            "Responde solo con JSON valido."
        ),
        "input": _build_alias_generation_prompt(tramite),
        "max_output_tokens": 250,
        "reasoning": {"effort": "low"},
        "text": {"verbosity": "low"},
    }

    response = httpx.post(
        f"{settings.openai_base_url}/responses",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45.0,
    )
    response.raise_for_status()

    return _extract_aliases_from_response(response.json())


def _serialize_aliases(values: list[str]) -> str | None:
    aliases = _deduplicate_aliases(values)
    if not aliases:
        return None
    return "\n".join(aliases)


def get_tramite_semantic_aliases(tramite: Tramite) -> list[str]:
    normalized_name = _normalize(tramite.nombre)
    normalized_slug = _normalize(tramite.slug)
    searchable_text = f"{normalized_name} {normalized_slug}"
    explicit_aliases = _split_alias_text(tramite.alias_ciudadanos)
    inferred_intent_aliases = _infer_intent_aliases(tramite)
    domain_rule_aliases = _get_domain_rule_aliases(tramite)

    inferred_aliases: list[str]

    if "cancelacion" in searchable_text and "contribuyentes" in searchable_text:
        inferred_aliases = [
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
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "sisben" in searchable_text:
        inferred_aliases = [
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
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "predial" in searchable_text:
        inferred_aliases = [
            "impuesto de casa",
            "impuesto de vivienda",
            "impuesto de hogar",
            "impuesto de predio",
            "casa",
            "vivienda",
            "predio",
            "propiedad",
            "inmueble",
            "terreno",
            "catastro",
            "ficha catastral",
            "recibo predial",
            "lo de la casa",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "vehicular" in searchable_text:
        inferred_aliases = [
            "impuesto de carro",
            "impuesto de vehiculo",
            "impuesto de moto",
            "carro",
            "vehiculo",
            "automovil",
            "moto",
            "placa",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "facilidades" in searchable_text or "obligaciones-tributarias" in searchable_text:
        inferred_aliases = [
            "acuerdo de pago",
            "acuerdos de pago",
            "cuotas",
            "financiacion de deuda",
            "deuda de impuestos",
            "pagar por cuotas",
            "ponerse al dia",
            "mora",
            "deudor",
            "pagar atrasado",
            "pagos atrasados",
            "pago atrasado",
            "pago pendiente",
            "pagos pendientes",
            "deuda vencida",
            "pagar deuda",
            "ayuda con pagos",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "devolucion" in searchable_text or "compensacion" in searchable_text:
        inferred_aliases = [
            "devolver dinero",
            "devolver plata",
            "reintegro",
            "reembolso",
            "pago en exceso",
            "pago por error",
            "pague de mas",
            "me cobraron de mas",
            "saldo a favor",
            "compensar saldo",
            "devolucion de pago",
            "recuperar dinero pagado",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if (
        "registro" in searchable_text
        and "contribuyentes" in searchable_text
        and "modificacion" not in searchable_text
        and "cancelacion" not in searchable_text
    ):
        inferred_aliases = [
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
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "modificacion" in searchable_text and "contribuyentes" in searchable_text:
        inferred_aliases = [
            "modificar registro",
            "actualizar registro",
            "cambiar datos",
            "actualizar datos del negocio",
            "cambio de direccion",
            "cambio de propietario",
            "cambio de actividad",
            "modificar industria y comercio",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "industria" in searchable_text and "comercio" in searchable_text:
        inferred_aliases = [
            "industria y comercio",
            "impuesto de industria y comercio",
            "declaracion de industria y comercio",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "espectaculos" in searchable_text:
        inferred_aliases = [
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
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "alumbrado" in searchable_text:
        inferred_aliases = [
            "alumbrado publico",
            "servicio de alumbrado",
            "impuesto de alumbrado",
            "iluminacion publica",
            "luz publica",
            "recibo de luz",
            "servicio de la luz",
            "lo de la luz",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "paz" in searchable_text and "salvo" in searchable_text:
        inferred_aliases = [
            "paz y salvo",
            "certificado paz y salvo",
            "estar al dia",
            "certificado de impuestos",
            "paz y salbo",
            "certificado de deuda",
            "debo impuestos",
            "sacar paz y salvo",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    if "licencia" in searchable_text and "transito" in searchable_text:
        inferred_aliases = [
            "duplicado licencia",
            "duplicado de licencia de transito",
            "tarjeta de propiedad",
            "se me perdio la licencia",
            "copia licencia de transito",
        ]
        return _deduplicate_aliases(
            [
                *explicit_aliases,
                *inferred_intent_aliases,
                *domain_rule_aliases,
                *inferred_aliases,
            ]
        )

    return _deduplicate_aliases(
        [
            *explicit_aliases,
            *inferred_intent_aliases,
            *domain_rule_aliases,
        ]
    )


def build_tramite_embedding_text(tramite: Tramite) -> str:
    aliases = get_tramite_semantic_aliases(tramite)
    parts = [
        f"Nombre del tramite: {tramite.nombre}",
        f"Descripcion: {tramite.descripcion or 'Sin descripcion.'}",
        f"Requisitos: {tramite.requisitos or 'Sin requisitos registrados.'}",
        f"A quien va dirigido: {tramite.dirigido_a or 'Sin destinatario registrado.'}",
        f"Pasos: {tramite.pasos or 'Sin pasos registrados.'}",
        f"Tiempo estimado: {tramite.tiempo_estimado or 'Sin tiempo estimado registrado.'}",
        f"Medio de seguimiento: {tramite.medio_seguimiento or 'Sin medio de seguimiento registrado.'}",
        f"Normatividad: {tramite.normatividad or 'Sin normatividad registrada.'}",
        f"Enlace Click Aqui: {tramite.enlace_click_aqui or 'Sin enlace especifico registrado.'}",
        f"Costo: {tramite.costo or 'Sin costo registrado.'}",
        f"Horario: {tramite.horario or 'Sin horario registrado.'}",
        f"Dependencia: {tramite.dependencia}",
    ]

    if aliases:
        parts.append(
            "Equivalencias y sinonimos usados por la ciudadania: "
            + ", ".join(aliases),
        )

    return "\n".join(parts)


def generate_embedding(text: str) -> list[float]:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY no configurada. Define la clave en backend/.env para generar embeddings."
        )

    payload: dict[str, Any] = {
        "model": settings.embedding_model,
        "input": text,
        "encoding_format": "float",
        "dimensions": settings.embedding_dimensions,
    }

    response = httpx.post(
        f"{settings.openai_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()

    data = response.json()
    return data["data"][0]["embedding"]


def update_tramite_embedding(db: Session, tramite: Tramite) -> Tramite:
    generated_aliases: list[str] = []
    try:
        generated_aliases = _filter_generated_aliases(
            tramite,
            generate_citizen_aliases(tramite),
        )
    except Exception:
        generated_aliases = []

    merged_aliases = _deduplicate_aliases(
        [
            *_split_alias_text(tramite.alias_ciudadanos),
            *generated_aliases,
            *_get_domain_rule_aliases(tramite),
            *_infer_intent_aliases(tramite),
        ]
    )
    tramite.alias_ciudadanos = _serialize_aliases(merged_aliases)

    embedding_text = build_tramite_embedding_text(tramite)
    tramite.embedding_vector = generate_embedding(embedding_text)
    db.add(tramite)
    db.commit()
    db.refresh(tramite)
    return tramite
