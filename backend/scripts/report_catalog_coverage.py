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


def _is_real_catalog_tramite(tramite: Tramite) -> bool:
    slug = (tramite.slug or "").lower()
    nombre = (tramite.nombre or "").lower()
    return not (
        slug.startswith("test-")
        or "test-" in slug
        or nombre.startswith("test ")
        or "test-" in nombre
    )


def _level_bucket(score: int) -> str:
    if score < 55:
        return "critico"
    if score < 70:
        return "en_riesgo"
    if score < 85:
        return "estable"
    return "fuerte"


def main() -> None:
    db = SessionLocal()
    try:
        all_tramites = db.scalars(
            select(Tramite).where(
                not_(
                    or_(
                        Tramite.slug.like("test-%"),
                        Tramite.slug.like("%test-%"),
                        Tramite.nombre.like("Test %"),
                        Tramite.nombre.like("%test-%"),
                    )
                )
            )
        ).all()

        real_tramites = [tramite for tramite in all_tramites if _is_real_catalog_tramite(tramite)]
        active_tramites = sorted(
            [tramite for tramite in real_tramites if tramite.activo],
            key=lambda item: item.nombre,
        )
        inactive_tramites = sorted(
            [tramite for tramite in real_tramites if not tramite.activo],
            key=lambda item: item.nombre,
        )

        reports = [(tramite, assess_tramite_quality(tramite)) for tramite in active_tramites]
        coverage_levels = {"critico": 0, "en_riesgo": 0, "estable": 0, "fuerte": 0}
        scope_summary = {"tributario": 0, "fuera_de_foco": 0, "sin_contexto": 0}

        for _, report in reports:
            coverage_levels[_level_bucket(report.score)] += 1
            scope_summary[report.scope_status] = scope_summary.get(report.scope_status, 0) + 1

        print("# Evidencia de cobertura del catalogo")
        print()
        print("## Resumen general")
        print(f"- Total de tramites reales evaluados: {len(real_tramites)}")
        print(f"- Tramites activos en el catalogo ciudadano: {len(active_tramites)}")
        print(f"- Tramites desactivados en el panel admin: {len(inactive_tramites)}")
        print()
        print("## Calidad semantica del catalogo activo")
        print(f"- Fuertes: {coverage_levels['fuerte']}")
        print(f"- Estables: {coverage_levels['estable']}")
        print(f"- En riesgo: {coverage_levels['en_riesgo']}")
        print(f"- Criticos: {coverage_levels['critico']}")
        print()
        print("## Foco institucional del catalogo activo")
        print(f"- En foco tributario: {scope_summary.get('tributario', 0)}")
        print(f"- Fuera de foco: {scope_summary.get('fuera_de_foco', 0)}")
        print(f"- Sin contexto suficiente: {scope_summary.get('sin_contexto', 0)}")
        print()
        print("## Cobertura operativa")
        print("- El asistente ya consulta tramites activos desde la base institucional.")
        print("- El panel admin ya permite crear, editar, desactivar y reactivar tramites.")
        print("- Los tramites desactivados se conservan en una vista administrativa separada.")
        print("- Cada tramite expone evaluacion semantica para detectar fichas debiles.")
        print()
        print("## Muestra de tramites activos cubiertos")
        for tramite in active_tramites[:12]:
            print(f"- ID {tramite.id}: {tramite.nombre}")
        print()
        if inactive_tramites:
            print("## Muestra de tramites desactivados")
            for tramite in inactive_tramites[:8]:
                print(f"- ID {tramite.id}: {tramite.nombre}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
