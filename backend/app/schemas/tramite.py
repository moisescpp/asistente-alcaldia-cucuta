from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().split())


class TramiteBase(BaseModel):
    nombre: str
    slug: str
    descripcion: str | None = None
    requisitos: str | None = None
    costo: str | None = None
    horario: str | None = None
    dependencia: str
    fuente_url: str | None = None
    activo: bool = True

    @field_validator(
        "nombre",
        "slug",
        "descripcion",
        "requisitos",
        "costo",
        "horario",
        "dependencia",
        "fuente_url",
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
    costo: str | None = None
    horario: str | None = None
    dependencia: str | None = None
    fuente_url: str | None = None
    activo: bool | None = None

    @field_validator(
        "nombre",
        "slug",
        "descripcion",
        "requisitos",
        "costo",
        "horario",
        "dependencia",
        "fuente_url",
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

    model_config = ConfigDict(from_attributes=True)
