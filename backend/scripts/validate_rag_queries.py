from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services.consulta_service import process_consulta


SUCCESS_STATES = {
    "Coincidencias encontradas",
    "Coincidencias semanticas encontradas",
}


@dataclass(frozen=True)
class ValidationCase:
    question: str
    category: str
    expected_status: str
    expected_principal_contains: str | None = None
    expected_response_contains: str | None = None


VALIDATION_CASES = [
    ValidationCase(
        question="Quiero informacion sobre impuesto predial",
        category="directa",
        expected_status="positiva",
        expected_principal_contains="predial",
    ),
    ValidationCase(
        question="Necesito saber los requisitos del impuesto predial",
        category="directa",
        expected_status="positiva",
        expected_principal_contains="predial",
    ),
    ValidationCase(
        question="casa",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="predial",
    ),
    ValidationCase(
        question="vivienda",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="predial",
    ),
    ValidationCase(
        question="Como funcionan las facilidades de pago",
        category="directa",
        expected_status="positiva",
        expected_principal_contains="facilidades de pago",
    ),
    ValidationCase(
        question="Quiero informacion sobre acuerdos de pago",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="facilidades de pago",
    ),
    ValidationCase(
        question="pagar atrasado",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="facilidades de pago",
    ),
    ValidationCase(
        question="ayuda con pagos",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="facilidades de pago",
    ),
    ValidationCase(
        question="Necesito saber sobre devolucion de pagos en exceso",
        category="directa",
        expected_status="positiva",
        expected_principal_contains="devolucion",
    ),
    ValidationCase(
        question="Tramite para devolver pagos realizados por error",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="devolucion",
    ),
    ValidationCase(
        question="Impuesto vehicular",
        category="directa",
        expected_status="positiva",
        expected_principal_contains="vehicular",
        expected_response_contains="Informacion pendiente en el sistema:",
    ),
    ValidationCase(
        question="carro",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="vehicular",
    ),
    ValidationCase(
        question="moto",
        category="lenguaje ciudadano",
        expected_status="positiva",
        expected_principal_contains="vehicular",
    ),
    ValidationCase(
        question="Necesito informacion de transito sobre impuesto vehicular",
        category="larga",
        expected_status="positiva",
        expected_principal_contains="vehicular",
    ),
    ValidationCase(
        question="Impuesto aeroportuario",
        category="negativa",
        expected_status="Sin coincidencias en la base actual",
    ),
    ValidationCase(
        question="licencia conduccion",
        category="negativa",
        expected_status="Sin coincidencias en la base actual",
    ),
    ValidationCase(
        question="permiso construccion",
        category="negativa",
        expected_status="Sin coincidencias en la base actual",
    ),
    ValidationCase(
        question="impuestos",
        category="ambigua",
        expected_status="Consulta demasiado general",
    ),
    ValidationCase(
        question="luz",
        category="ambigua",
        expected_status="Consulta demasiado general",
    ),
    ValidationCase(
        question="publico",
        category="ambigua",
        expected_status="Consulta demasiado general",
    ),
]


def _status_matches(case: ValidationCase, actual_status: str) -> bool:
    if case.expected_status == "positiva":
        return actual_status in SUCCESS_STATES
    return actual_status == case.expected_status


def main() -> None:
    db = SessionLocal()
    failures: list[str] = []

    try:
        tramites = db.scalars(
            select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre),
        ).all()

        print("Bateria final de validacion RAG")
        print("=" * 50)

        for index, case in enumerate(VALIDATION_CASES, start=1):
            result = process_consulta(db, case.question, tramites)
            principal = (
                result.tramite_principal.nombre
                if result.tramite_principal is not None
                else "Sin tramite principal"
            )

            checks: list[tuple[str, bool]] = [
                ("estado", _status_matches(case, result.mensaje_estado)),
            ]

            if case.expected_principal_contains is not None:
                checks.append(
                    (
                        "tramite_principal",
                        result.tramite_principal is not None
                        and case.expected_principal_contains.lower()
                        in result.tramite_principal.nombre.lower(),
                    ),
                )

            if case.expected_response_contains is not None:
                checks.append(
                    (
                        "respuesta",
                        case.expected_response_contains in result.respuesta,
                    ),
                )

            passed = all(ok for _, ok in checks)
            marker = "PASS" if passed else "FAIL"

            print(f"\nCaso {index} [{case.category}] - {marker}")
            print(f"Consulta: {case.question}")
            print(f"Estado esperado: {case.expected_status}")
            print(f"Estado obtenido: {result.mensaje_estado}")
            print(f"Principal obtenido: {principal}")

            if not passed:
                failed_checks = ", ".join(name for name, ok in checks if not ok)
                failures.append(
                    f"Caso {index} ({case.question}) fallo en: {failed_checks}",
                )
                print(f"Detalle del fallo: {failed_checks}")

        print("\nResumen")
        print("-" * 50)
        print(f"Total de casos: {len(VALIDATION_CASES)}")
        print(f"Casos superados: {len(VALIDATION_CASES) - len(failures)}")
        print(f"Casos fallidos: {len(failures)}")

        if failures:
            print("\nFallos detectados:")
            for failure in failures:
                print(f"- {failure}")
            raise SystemExit(1)

        print("\nResultado general: bateria superada")
    finally:
        db.close()


if __name__ == "__main__":
    main()
