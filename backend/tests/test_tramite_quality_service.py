from app.services.tramite_quality_service import assess_tramite_quality, validate_tramite_payload


def build_payload(**overrides) -> dict:
    payload = {
        "nombre": "Actualizacion de Informacion SISBEN",
        "slug": "actualizacion-informacion-sisben",
        "descripcion": (
            "Permite corregir o actualizar la informacion registrada en la ficha del "
            "hogar para mantener el SISBEN alineado con la realidad del nucleo familiar."
        ),
        "requisitos": (
            "Documento de identidad, soporte del cambio reportado, ficha SISBEN y "
            "documentos del grupo familiar cuando aplique."
        ),
        "costo": "Sin costo",
        "horario": "Lunes a viernes",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://example.com/sisben",
        "embedding_vector": [0.1, 0.2, 0.3],
    }
    payload.update(overrides)
    return payload


def test_validate_tramite_payload_blocks_generic_or_weak_content() -> None:
    payload = build_payload(
        descripcion="Consulta orientativa del tramite.",
        requisitos="Documento.",
        fuente_url="",
    )

    blocking_issues = validate_tramite_payload(payload)

    assert any("descripcion" in issue for issue in blocking_issues)
    assert any("requisitos" in issue for issue in blocking_issues)


def test_quality_report_recognizes_hacienda_context_from_dependency_and_requirements() -> None:
    report = assess_tramite_quality(build_payload())

    assert report.score >= 80
    assert report.scope_status == "tributario"
    assert not any("rentas e impuestos" in alert for alert in report.alerts)
    assert "base semantica" in report.recommended_action.lower()


def test_quality_report_flags_out_of_scope_catalog_entries() -> None:
    report = assess_tramite_quality(
        build_payload(
            nombre="Duplicado de licencia de transito",
            slug="duplicado-licencia-transito",
            descripcion=(
                "Permite solicitar una nueva licencia de transito cuando el ciudadano "
                "pierde el documento o requiere actualizarlo por deterioro."
            ),
            requisitos=(
                "Documento de identidad, tarjeta de propiedad y soporte del motivo de la "
                "solicitud."
            ),
            dependencia="Secretaria de Movilidad",
        )
    )

    assert any("rentas e impuestos" in alert for alert in report.alerts)
    assert report.scope_status == "fuera_de_foco"
    assert "catalogo institucional" in report.recommended_action.lower()


def test_validate_tramite_payload_allows_specific_description_even_if_it_starts_with_tramite_para() -> None:
    payload = build_payload(
        descripcion=(
            "Tramite para corregir o actualizar datos del impuesto predial cuando el "
            "propietario detecta errores en identificacion del predio, titular o direccion."
        ),
    )

    blocking_issues = validate_tramite_payload(payload)

    assert not any("descripcion suena generica" in issue.lower() for issue in blocking_issues)
