from app.database import SessionLocal
from app.models import Tramite


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
    assert len(data["tramites_relacionados"]) == max(data["total_resultados"] - 1, 0)
    if data["tramites_relacionados"]:
        assert len(data["sugerencias"]) >= 1
    else:
        assert data["sugerencias"] == []
    assert "Tramite principal:" in data["respuesta"]
    assert "Datos registrados:" in data["respuesta"]
    assert "- Fuente oficial:" in data["respuesta"]


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


def test_consulta_rejects_semantically_close_but_incorrect_topic(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Impuesto aeroportuario"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Sin coincidencias en la base actual"
    assert data["tramite_principal"] is None
    assert data["tramites_relacionados"] == []


def test_consulta_falls_back_to_text_when_tramite_has_no_embedding(
    client,
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-vehicular",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Consulta orientativa del impuesto vehicular.",
        dependencia="Secretaria de transito y movilidad",
    )
    creation_response = client.post("/api/admin/tramites", json=payload)
    tramite_id = creation_response.json()["id"]

    db = SessionLocal()
    try:
        tramite = db.get(Tramite, tramite_id)
        tramite.embedding_vector = None
        db.add(tramite)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Impuesto vehicular"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "vehicular" in data["tramite_principal"]["nombre"].lower()


def test_consulta_understands_citizen_synonym_for_house(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "casa"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()
    assert "Tambien pueden interesarte:" not in data["respuesta"]


def test_consulta_understands_citizen_synonym_for_car(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "carro"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "vehicular" in data["tramite_principal"]["nombre"].lower()
    assert "Datos registrados:" in data["respuesta"]
    assert "Informacion pendiente en el sistema:" in data["respuesta"]
    assert "No hay informacion registrada en el sistema para este campo." not in data["respuesta"]


def test_consulta_prioritizes_supported_payment_candidate(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "pagar atrasado"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "facilidades de pago" in data["tramite_principal"]["nombre"].lower()


def test_consulta_understands_payment_help_alias(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "ayuda con pagos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "facilidades de pago" in data["tramite_principal"]["nombre"].lower()


def test_consulta_prioritizes_vehicular_over_incidental_transit_matches(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion de transito sobre impuesto vehicular"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "vehicular" in data["tramite_principal"]["nombre"].lower()


def test_consulta_rejects_overly_generic_tax_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "impuestos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert "Puedes intentar con algo como:" in data["respuesta"]


def test_consulta_rejects_overly_generic_payment_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "pagar algo"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Sin coincidencias en la base actual"
    assert data["tramite_principal"] is None
    assert "Esta version del asistente esta enfocada en rentas e impuestos" in data["respuesta"]


def test_consulta_requests_more_specific_query_for_generic_public_term(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "publico"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1


def test_consulta_requests_more_specific_query_for_generic_light_term(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "luz"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1


def test_consulta_prioritizes_predial_for_requirements_question(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "¿Cuales son los requisitos para el impuesto predial?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()


def test_consulta_rejects_out_of_scope_transit_license_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "¿Cuanto cuesta el duplicado de la licencia de transito?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Sin coincidencias en la base actual"
    assert data["tramite_principal"] is None


def test_consulta_returns_industria_y_comercio_tramite_when_registered(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Como hago para el negocio, lo de industria y comercio"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] in {
        "Coincidencias encontradas",
        "Coincidencias semanticas encontradas",
    }
    assert data["tramite_principal"] is not None
    assert "industria y comercio" in data["tramite_principal"]["nombre"].lower()


def test_consulta_tolerates_typo_for_predial_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion del impuetso predial"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()


def test_consulta_tolerates_typo_for_vehicular_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "impuesto vehivular"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "vehicular" in data["tramite_principal"]["nombre"].lower()


def test_consulta_tolerates_typo_for_paz_y_salvo_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "paz y salbo"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "paz y salvo" in data["tramite_principal"]["nombre"].lower()
