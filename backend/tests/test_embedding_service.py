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


def test_modificacion_tramite_embedding_text_infers_change_language() -> None:
    tramite = build_tramite(
        "Modificacion en el Registro de Contribuyentes - Industria y Comercio",
        "modificacion-registro-contribuyentes-industria-comercio",
    )

    text = build_tramite_embedding_text(tramite)

    assert "cambios" in text
    assert "industria y comercio" in text
    assert "hacer cambios en industria y comercio" in text


def test_actualizacion_tramite_embedding_text_infers_edit_language_without_manual_aliases() -> None:
    tramite = build_tramite(
        "Actualizacion de datos del Registro Tributario Municipal",
        "actualizacion-datos-registro-tributario-municipal",
    )

    text = build_tramite_embedding_text(tramite)

    assert "actualizar" in text
    assert "editar" in text
    assert "registro tributario municipal" in text


def test_espectaculos_embedding_text_includes_event_language_without_manual_aliases() -> None:
    tramite = build_tramite(
        "Impuesto sobre Espectaculos Publicos",
        "impuesto-sobre-espectaculos-publicos",
    )

    text = build_tramite_embedding_text(tramite)

    assert "concierto" in text
    assert "eventos masivos" in text
    assert "papeles para concierto" in text


def test_generated_alias_filter_discards_generic_or_noisy_entries() -> None:
    from app.services.embedding_service import _filter_generated_aliases

    tramite = build_tramite(
        "Impuesto sobre Espectaculos Publicos",
        "impuesto-sobre-espectaculos-publicos",
    )
    tramite.descripcion = "Impuesto municipal aplicable a espectaculos publicos y eventos."

    aliases = _filter_generated_aliases(
        tramite,
        [
            "consulta sobre impuesto sobre espectaculos publicos",
            "1969 publicos articulo 223",
            "impuesto sobre espectaculos publicos",
            "eventos con boleteria",
        ],
    )

    assert "consulta sobre impuesto sobre espectaculos publicos" not in aliases
    assert "1969 publicos articulo 223" not in aliases
    assert "impuesto sobre espectaculos publicos" in aliases
