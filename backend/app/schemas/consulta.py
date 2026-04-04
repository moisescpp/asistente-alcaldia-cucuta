from pydantic import BaseModel, Field


class ConsultaRequest(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)


class ConsultaMatch(BaseModel):
    id: int
    nombre: str
    slug: str
    dependencia: str
    fuente_url: str | None = None


class ConsultaResponse(BaseModel):
    pregunta: str
    respuesta: str
    total_resultados: int
    tramites_relacionados: list[ConsultaMatch]
