from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import not_, or_, select

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services.tramite_quality_service import assess_tramite_quality


def _level_bucket(score: int) -> str:
    if score < 55:
        return "critico"
    if score < 75:
        return "intermedio"
    return "fuerte"


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
            .order_by(Tramite.nombre.asc())
        ).all()

        reports = [
            (tramite, assess_tramite_quality(tramite))
            for tramite in tramites
        ]
        ranked_reports = sorted(reports, key=lambda item: (item[1].score, item[0].nombre))

        print("Auditoria de calidad de tramites activos")
        print("=" * 60)
        print(f"Total de tramites evaluados: {len(ranked_reports)}")
        print()

        for tramite, report in ranked_reports[:12]:
            print(
                f"[{report.score:03d}] ID {tramite.id} | {tramite.nombre} | slug={tramite.slug}"
            )
            print("  Nivel: " + report.level)
            print("  Alertas: " + "; ".join(report.alerts or ["sin alertas relevantes"]))

        summary = {"critico": 0, "intermedio": 0, "fuerte": 0}
        for _, report in ranked_reports:
            summary[_level_bucket(report.score)] += 1

        print()
        print("Resumen rapido")
        print("-" * 60)
        print(f"Criticos (<55): {summary['critico']}")
        print(f"Intermedios (55-74): {summary['intermedio']}")
        print(f"Fuertes (>=75): {summary['fuerte']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
