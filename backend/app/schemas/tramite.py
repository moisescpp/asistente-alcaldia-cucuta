from datetime import datetime
import html
import re

from pydantic import BaseModel, ConfigDict, field_validator


HTML_PATTERN = re.compile(
    r"<!--|-->|<!\[CDATA\[|<!DOCTYPE|</?\s*[a-zA-Z][\w:-]*(?:\s+[^<>]*)?/?>",
    re.IGNORECASE,
)


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    cleaned = " ".join(value.strip().split())
    if HTML_PATTERN.search(cleaned) or HTML_PATTERN.search(html.unescape(cleaned)):
        raise ValueError("No se permite incluir HTML en los campos del tramite.")

    return cleaned


class TramiteBase(BaseModel):
    nombre: str
    slug: str
    descripcion: str | None = None
    requisitos: str | None = None
    dirigido_a: str | None = None
    pasos: str | None = None
    tiempo_estimado: str | None = None
    medio_seguimiento: str | None = None
    normatividad: str | None = None
    costo: str | None = None
    horario: str | None = None
    dependencia: str
    fuente_url: str | None = None
    enlace_click_aqui: str | None = None
    activo: bool = True

    @field_validator(
        "nombre",
        "slug",
        "descripcion",
        "requisitos",
        "dirigido_a",
        "pasos",
        "tiempo_estimado",
        "medio_seguimiento",
        "normatividad",
        "costo",
        "horario",
        "dependencia",
        "fuente_url",
        "enlace_click_aqui",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        return _clean_string(value)


class TramiteCreate(TramiteBase):
    pass


class TramiteUpdate(BaseModel):
    nombre: str | None = None
    slug: str | None = None
    descripcion: str | None = None
    requisitos: str | None = None
    dirigido_a: str | None = None
    pasos: str | None = None
    tiempo_estimado: str | None = None
    medio_seguimiento: str | None = None
    normatividad: str | None = None
    costo: str | None = None
    horario: str | None = None
    dependencia: str | None = None
    fuente_url: str | None = None
    enlace_click_aqui: str | None = None
    activo: bool | None = None

    @field_validator(
        "nombre",
        "slug",
        "descripcion",
        "requisitos",
        "dirigido_a",
        "pasos",
        "tiempo_estimado",
        "medio_seguimiento",
        "normatividad",
        "costo",
        "horario",
        "dependencia",
        "fuente_url",
        "enlace_click_aqui",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        return _clean_string(value)


class TramiteRead(TramiteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    semantic_quality_score: int = 0
    semantic_quality_level: str = "sin_datos"
    semantic_quality_alerts: list[str] = []
    semantic_scope_status: str = "sin_datos"
    semantic_recommended_action: str = ""

    model_config = ConfigDict(from_attributes=True)
