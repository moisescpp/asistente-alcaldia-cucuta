from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.models import Tramite


def build_tramite_context(tramites: list[Tramite]) -> str:
    context_blocks = []

    for index, tramite in enumerate(tramites, start=1):
        context_blocks.append(
            "\n".join(
                [
                    f"Tramite {index}: {tramite.nombre}",
                    f"Dependencia: {tramite.dependencia}",
                    f"Descripcion: {tramite.descripcion or 'Sin descripcion registrada.'}",
                    f"Requisitos: {tramite.requisitos or 'Sin requisitos registrados.'}",
                    f"Costo: {tramite.costo or 'Sin costo registrado.'}",
                    f"Horario: {tramite.horario or 'Sin horario registrado.'}",
                    f"Fuente: {tramite.fuente_url or 'Sin fuente registrada.'}",
                ]
            )
        )

    return "\n\n".join(context_blocks)


def _extract_output_text(data: dict[str, Any]) -> str:
    output_items = data.get("output", [])
    text_fragments: list[str] = []

    for item in output_items:
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                text_fragments.append(content["text"].strip())

    return "\n\n".join(fragment for fragment in text_fragments if fragment).strip()


def _sanitize_output_text(output_text: str, *, total_tramites: int) -> str:
    if total_tramites > 1:
        return output_text.strip()

    normalized = output_text.replace("\r\n", "\n")
    marker = "Tambien pueden interesarte"

    if marker in normalized:
        normalized = normalized.split(marker, 1)[0].rstrip()

    return normalized.strip()


def generate_rag_response(
    *,
    pregunta: str,
    tramites: list[Tramite],
) -> str:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY no configurada. Define la clave en backend/.env para generar respuestas RAG."
        )

    context = build_tramite_context(tramites)

    payload: dict[str, Any] = {
        "model": settings.response_model,
        "instructions": (
            "Eres un asistente institucional de tramites estrella de rentas e impuestos "
            "de la Alcaldia de San Jose de Cucuta. Responde en espanol claro, sin inventar "
            "informacion, usando solo el contexto entregado. Si el contexto no alcanza, dilo "
            "de manera breve y orienta al ciudadano a validar en la fuente oficial. "
            "Debes priorizar claramente el tramite mas relevante y no mezclar todos los tramites "
            "al mismo nivel."
        ),
        "input": (
            f"Pregunta del ciudadano: {pregunta}\n\n"
            f"Contexto recuperado:\n{context}\n\n"
            "Redacta la respuesta con esta estructura exacta:\n"
            "1. Una linea breve que diga cual es el tramite principal.\n"
            "2. Una seccion corta con: requisitos, costo, horario, dependencia y fuente oficial.\n"
            "3. Si hay otros tramites en el contexto, agregalos al final bajo el titulo "
            "'Tambien pueden interesarte', en una lista corta.\n"
            "3.1. Si solo existe un tramite en el contexto, no escribas la seccion "
            "'Tambien pueden interesarte' ni agregues aclaraciones sobre ausencia de resultados.\n"
            "4. Usa saltos de linea y vietas simples para que la respuesta sea facil de leer.\n"
            "5. No inventes datos ni agregues tramites fuera del contexto recuperado."
        ),
        "max_output_tokens": settings.response_max_output_tokens,
        "reasoning": {"effort": settings.response_reasoning_effort},
        "text": {"verbosity": settings.response_text_verbosity},
    }

    response = httpx.post(
        f"{settings.openai_base_url}/responses",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()

    data = response.json()
    output_text = _sanitize_output_text(
        _extract_output_text(data),
        total_tramites=len(tramites),
    )

    if not output_text:
        raise ValueError("La API de OpenAI no devolvio texto en la respuesta RAG.")

    return output_text
