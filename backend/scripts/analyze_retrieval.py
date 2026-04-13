from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import not_, or_, select

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services.embedding_service import generate_embedding
from app.services.consulta_service import _candidate_support


ANALYSIS_QUERIES = [
    "casa",
    "vivienda",
    "carro",
    "moto",
    "pagar atrasado",
    "acuerdo de pago",
    "devolver dinero",
    "reembolso",
    "impuesto aeroportuario",
    "pagar algo",
    "ayuda con pagos",
    "impuestos",
    "¿Cuales son los requisitos para el impuesto predial?",
    "¿Cuanto cuesta el duplicado de la licencia de transito?",
    "Como hago para el negocio, lo de industria y comercio",
]

TOP_RESULTS = 5


def main() -> None:
    db = SessionLocal()

    try:
        print("Analisis de retrieval semantico")
        print("=" * 50)

        for question in ANALYSIS_QUERIES:
            embedding = generate_embedding(question)
            distance = Tramite.embedding_vector.cosine_distance(embedding).label("distance")
            rows = db.execute(
                select(Tramite.nombre, distance)
                .where(
                    Tramite.activo.is_(True),
                    Tramite.embedding_vector.is_not(None),
                    not_(
                        or_(
                            Tramite.slug.like("test-%"),
                            Tramite.nombre.like("Test %"),
                        )
                    ),
                )
                .order_by(distance)
                .limit(TOP_RESULTS),
            ).all()

            print(f"\nConsulta: {question}")
            for index, (name, score) in enumerate(rows, start=1):
                print(f"{index}. {score:.4f} -> {name}")
                tramite = db.scalars(
                    select(Tramite).where(Tramite.nombre == name),
                ).first()
                if tramite is not None and question in {
                    "¿Cuales son los requisitos para el impuesto predial?",
                    "Como hago para el negocio, lo de industria y comercio",
                }:
                    print(f"   soporte={_candidate_support(question, tramite)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
