from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Tramite


def build_tramite_embedding_text(tramite: Tramite) -> str:
    parts = [
        f"Nombre del tramite: {tramite.nombre}",
        f"Descripcion: {tramite.descripcion or 'Sin descripcion.'}",
        f"Requisitos: {tramite.requisitos or 'Sin requisitos registrados.'}",
        f"Costo: {tramite.costo or 'Sin costo registrado.'}",
        f"Horario: {tramite.horario or 'Sin horario registrado.'}",
        f"Dependencia: {tramite.dependencia}",
    ]
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
