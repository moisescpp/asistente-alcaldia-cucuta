from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsultaLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pregunta: str
    mensaje_estado: str
    origen_respuesta: str
    total_resultados: int
    tramite_principal_id: int | None = None
    tramite_principal_nombre: str | None = None
    created_at: datetime
