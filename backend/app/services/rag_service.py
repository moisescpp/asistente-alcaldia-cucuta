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
            "de manera breve y orienta al ciudadano a validar en la fuente oficial."
        ),
        "input": (
            f"Pregunta del ciudadano: {pregunta}\n\n"
            f"Contexto recuperado:\n{context}\n\n"
            "Redacta una respuesta corta, util y bien organizada para el ciudadano."
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
    output_text = _extract_output_text(data)

    if not output_text:
        raise ValueError("La API de OpenAI no devolvio texto en la respuesta RAG.")

    return output_text
