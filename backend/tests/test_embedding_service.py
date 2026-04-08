from app.models import Tramite
from app.services.embedding_service import build_tramite_embedding_text


def build_tramite(nombre: str, slug: str) -> Tramite:
    return Tramite(
        nombre=nombre,
        slug=slug,
        descripcion=None,
        requisitos=None,
        costo=None,
        horario=None,
        dependencia="Dependencia de prueba",
        fuente_url=None,
        activo=True,
    )


def test_predial_embedding_text_includes_citizen_synonyms() -> None:
    tramite = build_tramite(
        "Impuesto predial unificado",
        "impuesto-predial-unificado",
    )

    text = build_tramite_embedding_text(tramite)

    assert "casa" in text
    assert "vivienda" in text
    assert "predio" in text


def test_vehicular_embedding_text_includes_citizen_synonyms() -> None:
    tramite = build_tramite(
        "Impuesto vehicular",
        "85",
    )

    text = build_tramite_embedding_text(tramite)

    assert "carro" in text
    assert "moto" in text
    assert "vehiculo" in text
