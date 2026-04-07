def build_payload(slug: str, **overrides) -> dict:
    payload = {
        "nombre": f"Test consulta {slug}",
        "slug": slug,
        "descripcion": "Tramite de prueba para consultas.",
        "requisitos": "Documento de identidad y soporte.",
        "costo": "Sin costo",
        "horario": "Lunes a viernes",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://example.com/consulta",
        "activo": True,
    }
    payload.update(overrides)
    return payload


def test_consulta_returns_main_match_and_related_results(client, test_slug_prefix) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-predial",
        nombre=f"Impuesto predial de prueba {test_slug_prefix}",
        descripcion="Consulta orientativa del impuesto predial de prueba.",
        requisitos="Documento de identidad y referencia catastral.",
    )
    client.post("/api/admin/tramites", json=payload)

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion sobre impuesto predial"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] in {
        "Coincidencias encontradas",
        "Coincidencias semanticas encontradas",
    }
    assert data["total_resultados"] >= 1
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()
    assert data["tramites_relacionados"]
    assert data["sugerencias"] == []


def test_consulta_returns_suggestions_when_question_is_too_short(client) -> None:
    response = client.post("/api/consulta", json={"pregunta": "hi"})

    assert response.status_code == 422


def test_consulta_returns_no_match_message_and_suggestions(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "xilofono intergalactico kriptonita"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Sin coincidencias en la base actual"
    assert data["total_resultados"] == 0
    assert data["tramite_principal"] is None
    assert data["tramites_relacionados"] == []
    assert len(data["sugerencias"]) >= 1
