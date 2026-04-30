from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import not_, or_, select

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services.consulta_service import process_consulta


PERFORMANCE_CASES = [
    "Quiero informacion sobre impuesto predial",
    "cambios en industria y comercio",
    "Papeles para hacer un concierto en Cucuta",
    "impuestos",
    "paz y salbo",
    "informacion de impuetos",
]
RUNS_PER_CASE = 3
AVG_TARGET_SECONDS = 1.5
MAX_TARGET_SECONDS = 2.5


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> None:
    db = SessionLocal()
    try:
        tramites = db.scalars(
            select(Tramite)
            .where(
                Tramite.activo.is_(True),
                not_(
                    or_(
                        Tramite.slug.like("test-%"),
                        Tramite.slug.like("%test-%"),
                        Tramite.nombre.like("Test %"),
                        Tramite.nombre.like("%test-%"),
                    )
                ),
            )
            .order_by(Tramite.nombre)
        ).all()

        print("# Evidencia de rendimiento")
        print()
        print("## Configuracion de la prueba")
        print(f"- Casos evaluados: {len(PERFORMANCE_CASES)}")
        print(f"- Corridas por caso: {RUNS_PER_CASE}")
        print(f"- Meta local de promedio: <= {AVG_TARGET_SECONDS:.2f} s")
        print(f"- Meta local de maximo: <= {MAX_TARGET_SECONDS:.2f} s")
        print()

        timings: list[float] = []

        for question in PERFORMANCE_CASES:
            case_timings: list[float] = []
            for _ in range(RUNS_PER_CASE):
                started = time.perf_counter()
                process_consulta(db, question, tramites)
                elapsed = time.perf_counter() - started
                case_timings.append(elapsed)
                timings.append(elapsed)

            print(f"## Caso: {question}")
            print(f"- Promedio: {statistics.mean(case_timings):.4f} s")
            print(f"- Minimo: {min(case_timings):.4f} s")
            print(f"- Maximo: {max(case_timings):.4f} s")
            print()

        average = statistics.mean(timings) if timings else 0.0
        median = statistics.median(timings) if timings else 0.0
        p95 = _percentile(timings, 0.95)
        maximum = max(timings) if timings else 0.0

        print("## Resumen general")
        print(f"- Tiempo promedio global: {average:.4f} s")
        print(f"- Mediana global: {median:.4f} s")
        print(f"- Percentil 95 aproximado: {p95:.4f} s")
        print(f"- Maximo global: {maximum:.4f} s")
        print()
        print("## Lectura tecnica")
        print(
            "- Promedio dentro de objetivo local: "
            + ("si" if average <= AVG_TARGET_SECONDS else "no")
        )
        print(
            "- Maximo dentro de objetivo local: "
            + ("si" if maximum <= MAX_TARGET_SECONDS else "no")
        )
        print(
            "- Esta evidencia sirve como linea base de rendimiento local para la validacion del proyecto."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
