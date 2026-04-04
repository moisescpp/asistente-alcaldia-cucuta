import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite


TRAMITES_INICIALES = [
    {
        "nombre": "Impuesto predial unificado",
        "slug": "impuesto-predial-unificado",
        "descripcion": "Consulta orientativa del tramite de impuesto predial unificado.",
        "requisitos": "Documento de identidad del solicitante y referencia catastral del predio.",
        "costo": "Segun liquidacion vigente.",
        "horario": "Lunes a viernes de 7:00 a. m. a 1:00 p. m.",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://cucuta.gov.co/tramites-y-servicios/",
        "activo": True,
    },
    {
        "nombre": "Registro de contribuyentes del impuesto de industria y comercio",
        "slug": "registro-contribuyentes-industria-comercio",
        "descripcion": "Registro inicial de contribuyentes del impuesto de industria y comercio.",
        "requisitos": "Documento de identidad, RUT y formulario de registro.",
        "costo": "Sin costo",
        "horario": "Lunes a viernes de 7:00 a. m. a 1:00 p. m.",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://cucuta.gov.co/tramites-y-servicios/",
        "activo": True,
    },
    {
        "nombre": "Facilidades de pago para los deudores de obligaciones tributarias",
        "slug": "facilidades-pago-obligaciones-tributarias",
        "descripcion": "Solicitud de acuerdos o facilidades de pago para obligaciones tributarias pendientes.",
        "requisitos": "Documento de identidad, solicitud formal y soporte de la obligacion.",
        "costo": "Sin costo",
        "horario": "Lunes a viernes de 7:00 a. m. a 1:00 p. m.",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://cucuta.gov.co/tramites-y-servicios/",
        "activo": True,
    },
    {
        "nombre": "Devolucion y/o compensacion de pagos en exceso y pagos de lo no debido",
        "slug": "devolucion-compensacion-pagos-exceso-no-debido",
        "descripcion": "Tramite para solicitar la devolucion o compensacion de pagos realizados en exceso.",
        "requisitos": "Solicitud escrita, documento de identidad y soportes de pago.",
        "costo": "Sin costo",
        "horario": "Lunes a viernes de 7:00 a. m. a 1:00 p. m.",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://cucuta.gov.co/tramites-y-servicios/",
        "activo": True,
    },
]


def main() -> None:
    with SessionLocal() as db:
        for tramite_data in TRAMITES_INICIALES:
            existing = db.scalar(
                select(Tramite).where(Tramite.slug == tramite_data["slug"])
            )
            if existing:
                continue

            db.add(Tramite(**tramite_data))

        db.commit()
        print("Seed completado.")


if __name__ == "__main__":
    main()
