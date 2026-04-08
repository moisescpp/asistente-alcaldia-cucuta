from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services.consulta_service import process_consulta


REAL_WORLD_QUESTIONS = [
    "Quiero informacion sobre impuesto predial",
    "Necesito saber los requisitos del impuesto predial",
    "Como funcionan las facilidades de pago",
    "Quiero informacion sobre acuerdos de pago",
    "Necesito saber sobre devolucion de pagos en exceso",
    "Como funciona la compensacion de pagos no debidos",
    "Impuesto vehicular",
    "Necesito informacion de transito sobre impuesto vehicular",
    "Impuesto aeroportuario",
    "Tramite para devolver pagos realizados por error",
]


def main() -> None:
    db = SessionLocal()

    try:
        tramites = db.scalars(
            select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre),
        ).all()

        print("Validacion funcional de consultas RAG")
        print("=" * 50)

        for index, question in enumerate(REAL_WORLD_QUESTIONS, start=1):
            result = process_consulta(db, question, tramites)
            principal = (
                result.tramite_principal.nombre
                if result.tramite_principal is not None
                else "Sin tramite principal"
            )

            print(f"\nCaso {index}: {question}")
            print(f"Estado: {result.mensaje_estado}")
            print(f"Principal: {principal}")
            print("Respuesta:")
            print(result.respuesta)
            print("-" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
