from pydantic import BaseModel, Field


class ConsultaRequest(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)


class ConsultaMatch(BaseModel):
    id: int
    nombre: str
    slug: str
    descripcion: str | None = None
    requisitos: str | None = None
    costo: str | None = None
    horario: str | None = None
    dependencia: str
    fuente_url: str | None = None


class ConsultaResponse(BaseModel):
    pregunta: str
    respuesta: str
    mensaje_estado: str
    total_resultados: int
    tramite_principal: ConsultaMatch | None = None
    tramites_relacionados: list[ConsultaMatch]
    sugerencias: list[str] = []
