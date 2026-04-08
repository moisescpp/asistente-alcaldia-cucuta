from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Tramite


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def get_tramite_semantic_aliases(tramite: Tramite) -> list[str]:
    normalized_name = _normalize(tramite.nombre)
    normalized_slug = _normalize(tramite.slug)
    searchable_text = f"{normalized_name} {normalized_slug}"

    if "predial" in searchable_text:
        return [
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
        ]

    if "vehicular" in searchable_text:
        return [
            "impuesto de carro",
            "impuesto de vehiculo",
            "impuesto de moto",
            "carro",
            "vehiculo",
            "automovil",
            "moto",
            "placa",
            "transito",
            "movilidad",
        ]

    if "facilidades" in searchable_text or "obligaciones-tributarias" in searchable_text:
        return [
            "acuerdo de pago",
            "cuotas",
            "financiacion de deuda",
            "deuda de impuestos",
            "pagar por cuotas",
            "ponerse al dia",
            "mora",
            "deudor",
        ]

    if "devolucion" in searchable_text or "compensacion" in searchable_text:
        return [
            "devolver dinero",
            "reintegro",
            "reembolso",
            "pago en exceso",
            "pago por error",
            "compensar saldo",
            "devolucion de pago",
            "recuperar dinero pagado",
        ]

    return []


def build_tramite_embedding_text(tramite: Tramite) -> str:
    aliases = get_tramite_semantic_aliases(tramite)
    parts = [
        f"Nombre del tramite: {tramite.nombre}",
        f"Descripcion: {tramite.descripcion or 'Sin descripcion.'}",
        f"Requisitos: {tramite.requisitos or 'Sin requisitos registrados.'}",
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
    embedding_text = build_tramite_embedding_text(tramite)
    tramite.embedding_vector = generate_embedding(embedding_text)
    db.add(tramite)
    db.commit()
    db.refresh(tramite)
    return tramite
