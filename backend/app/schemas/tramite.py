from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class TramiteRead(TramiteBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
