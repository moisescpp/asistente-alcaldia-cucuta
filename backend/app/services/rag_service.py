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
                    f"A quien va dirigido: {tramite.dirigido_a or 'Sin destinatario registrado.'}",
                    f"Pasos: {tramite.pasos or 'Sin pasos registrados.'}",
                    f"Tiempo estimado: {tramite.tiempo_estimado or 'Sin tiempo estimado registrado.'}",
                    f"Medio de seguimiento: {tramite.medio_seguimiento or 'Sin medio de seguimiento registrado.'}",
                    f"Normatividad: {tramite.normatividad or 'Sin normatividad registrada.'}",
                    f"Costo: {tramite.costo or 'Sin costo registrado.'}",
                    f"Horario: {tramite.horario or 'Sin horario registrado.'}",
                    f"Fuente: {tramite.fuente_url or 'Sin fuente registrada.'}",
                    f"Enlace Click Aqui: {tramite.enlace_click_aqui or 'Sin enlace especifico registrado.'}",
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
    normalized = output_text.replace("\r\n", "\n")
    marker = "Tambien pueden interesarte"

    if marker in normalized:
        normalized = normalized.split(marker, 1)[0].rstrip()

    cleaned_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "1.", "2.", "3.")):
            line = line.lstrip("-*0123456789. ").strip()
        if line:
            cleaned_lines.append(line)

    cleaned_text = " ".join(cleaned_lines).strip()
    if not cleaned_text:
        return ""

    sentence_count = 0
    collected: list[str] = []
    for character in cleaned_text:
        collected.append(character)
        if character in ".!?":
            sentence_count += 1
            if sentence_count >= 2:
                break

    trimmed_text = "".join(collected).strip()
    if trimmed_text and trimmed_text[-1] not in ".!?":
        trimmed_text = f"{trimmed_text}."

    return trimmed_text


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
            "Solo debes redactar una orientacion corta de maximo dos oraciones sobre el tramite "
            "principal, enfocada unicamente en el proposito del tramite y la dependencia responsable. "
            "No listes requisitos, costo, horario ni fuente; esos datos los agrega el sistema despues. "
            "No menciones documentos, pasos, canales, tiempos, actos administrativos ni acciones "
            "que no esten literalmente sustentadas en el contexto. No uses numeracion ni vietas. "
            "No inventes datos ni completes campos faltantes con suposiciones."
        ),
        "input": (
            f"Pregunta del ciudadano: {pregunta}\n\n"
            f"Contexto recuperado:\n{context}\n\n"
            "Redacta solo una breve orientacion inicial para el ciudadano sobre el tramite principal."
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
