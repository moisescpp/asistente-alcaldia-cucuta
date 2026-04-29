import unicodedata

import pytest

from app.database import SessionLocal
from app.main import app
from app.models import ConsultaLog, Tramite
from app.services.consulta_service import _build_no_match_suggestions


def build_payload(slug: str, **overrides) -> dict:
    payload = {
        "nombre": f"Test consulta {slug}",
        "slug": slug,
        "descripcion": (
            "Gestion tributaria temporal para consultas ciudadanas con contexto suficiente "
            "sobre impuestos y gestiones tributarias."
        ),
        "requisitos": (
            "Documento de identidad vigente, formulario diligenciado y soporte "
            "del caso tributario."
        ),
        "costo": "Sin costo",
        "horario": "Lunes a viernes",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://example.com/consulta",
        "activo": True,
    }
    payload.update(overrides)
    return payload


def normalize_assert_text(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def create_test_tramite(client, admin_headers: dict[str, str], slug: str, **overrides) -> dict:
    response = client.post(
        "/api/admin/tramites",
        json=build_payload(slug, **overrides),
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def has_active_catalog_term(term: str) -> bool:
    db = SessionLocal()
    try:
        tramites = db.query(Tramite).filter(Tramite.activo.is_(True)).all()
        needle = normalize_assert_text(term)
        return any(needle in normalize_assert_text(tramite.nombre) for tramite in tramites)
    finally:
        db.close()


def test_consulta_returns_main_match_and_related_results(client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-predial",
        nombre=f"Impuesto predial de prueba {test_slug_prefix}",
        descripcion="Consulta del impuesto predial municipal para casas, lotes y predios ubicados en la jurisdiccion local.",
        requisitos="Documento de identidad vigente, referencia catastral y datos del predio a consultar.",
    )

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


def test_no_match_suggestions_prioritize_similar_catalog_topics() -> None:
    tramites = [
        Tramite(
            id=1,
            nombre="Impuesto sobre Espectaculos Publicos",
            slug="espectaculos-publicos",
            descripcion="Pago para conciertos, eventos masivos, baile con orquesta y espectaculos publicos.",
            dependencia="Secretaria de Hacienda - Rentas e Impuestos",
            activo=True,
        ),
        Tramite(
            id=2,
            nombre="Impuesto predial",
            slug="predial",
            descripcion="Consulta del impuesto predial unificado.",
            dependencia="Secretaria de Hacienda - Rentas e Impuestos",
            activo=True,
        ),
        Tramite(
            id=3,
            nombre="Facilidades de pago",
            slug="facilidades-pago",
            descripcion="Acuerdos de pago para obligaciones tributarias.",
            dependencia="Secretaria de Hacienda - Rentas e Impuestos",
            activo=True,
        ),
    ]

    suggestions = _build_no_match_suggestions(
        "permiso cultural para concierto universitario",
        tramites,
    )

    assert suggestions
    assert suggestions[0] == "Consulta por Impuesto sobre Espectaculos Publicos"


def test_no_match_suggestions_return_distinct_catalog_options() -> None:
    tramites = [
        Tramite(id=1, nombre="Impuesto predial", slug="predial", descripcion="Predial", activo=True),
        Tramite(id=2, nombre="Facilidades de pago", slug="facilidades", descripcion="Pagos", activo=True),
        Tramite(id=3, nombre="Impuesto vehicular", slug="vehicular", descripcion="Vehiculos", activo=True),
        Tramite(id=4, nombre="Devolucion de pagos", slug="devolucion", descripcion="Devolucion", activo=True),
    ]

    suggestions = _build_no_match_suggestions(
        "xilofono intergalactico kriptonita",
        tramites,
    )

    assert len(suggestions) == 4
    assert len(set(suggestions)) == 4


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
    admin_headers,
    test_slug_prefix,
) -> None:
    creation_response = create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-vehicular",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Gestion del impuesto vehicular para carros, motos y otros vehiculos registrados por el contribuyente.",
        dependencia="Secretaria de transito y movilidad",
    )
    tramite_id = creation_response["id"]

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


def test_consulta_understands_citizen_synonym_for_car(client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-vehicular-carro",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Gestion del impuesto vehicular para carros, motos y otros vehiculos registrados por el contribuyente.",
        dependencia="Secretaria de transito y movilidad",
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "carro"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "vehicular" in data["tramite_principal"]["nombre"].lower()
    assert "Datos registrados:" in data["respuesta"]
    assert "Informacion pendiente en el sistema:" not in data["respuesta"]


def test_consulta_prioritizes_supported_payment_candidate(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-facilidades-pago",
        nombre=f"Facilidades de pago para obligaciones tributarias {test_slug_prefix}",
        descripcion=(
            "Gestion para solicitar acuerdos de pago, cuotas o alternativas para "
            "ponerse al dia con deudas tributarias vencidas o pagos atrasados."
        ),
        requisitos=(
            "Documento de identidad, solicitud formal y soporte de la deuda "
            "tributaria que se desea financiar."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "pagar atrasado"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "facilidades de pago" in data["tramite_principal"]["nombre"].lower()


def test_consulta_understands_payment_help_alias(client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-facilidades-ayuda",
        nombre=f"Facilidades de pago para obligaciones tributarias {test_slug_prefix}",
        descripcion=(
            "Gestion para pedir ayuda con pagos, acuerdos de pago y cuotas de "
            "impuestos pendientes ante la secretaria de hacienda."
        ),
        requisitos=(
            "Documento de identidad, solicitud formal y evidencia de las "
            "obligaciones tributarias pendientes."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "ayuda con pagos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "facilidades de pago" in data["tramite_principal"]["nombre"].lower()


def test_consulta_prioritizes_vehicular_over_incidental_transit_matches(client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-vehicular-transito",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Gestion del impuesto vehicular para carros, motos y placa dentro de la atencion tributaria municipal.",
        dependencia="Secretaria de transito y movilidad",
    )

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
    assert len(data["sugerencias"]) >= 1
    assert len(data["tramites_relacionados"]) >= 1


def test_consulta_rejects_overly_generic_tax_query_with_typo(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "immpuestos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1
    assert len(data["tramites_relacionados"]) >= 1


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
    assert len(data["tramites_relacionados"]) >= 1


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
    assert len(data["tramites_relacionados"]) >= 1


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
    if has_active_catalog_term("licencia"):
        pytest.skip("La base actual ya contiene tramites activos de licencia.")

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


def test_consulta_prioritizes_modificacion_for_change_language_in_industria_y_comercio(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    base_name = f"Registro de Contribuyentes Industria y Comercio {test_slug_prefix}"
    modification_name = f"Modificacion en el Registro de Contribuyentes Industria y Comercio {test_slug_prefix}"

    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-registro-ic",
        nombre=base_name,
        descripcion="Inscripcion de personas o empresas en el registro de contribuyentes de industria y comercio para iniciar obligaciones tributarias.",
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-modificacion-ic",
        nombre=modification_name,
        descripcion="Actualizacion de datos en el registro de contribuyentes de industria y comercio cuando cambia informacion del negocio o responsable.",
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": f"Necesito hacer cambios en industria y comercio {test_slug_prefix}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "modificacion" in data["tramite_principal"]["nombre"].lower()


def test_consulta_matches_espectaculos_publicos_for_concert_language(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-espectaculos-publicos",
        nombre=f"Impuesto sobre Espectaculos Publicos {test_slug_prefix}",
        descripcion=(
            "Gestion para consultar y pagar el impuesto municipal sobre "
            "espectaculos publicos, conciertos, festivales y eventos masivos."
        ),
        requisitos="Documento del organizador y soporte del evento.",
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Papeles para hacer un concierto en Cucuta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert "espect" in principal_name
    assert "public" in principal_name


def test_consulta_matches_espectaculos_publicos_for_mass_event_language(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-espectaculos-masivos",
        nombre=f"Impuesto sobre Espectaculos Publicos {test_slug_prefix}",
        descripcion=(
            "Gestion para liquidar o pagar el impuesto de espectaculos publicos "
            "aplicable a conciertos y eventos masivos."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "impuesto para eventos masivos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert "espect" in principal_name
    assert "public" in principal_name


def test_consulta_matches_espectaculos_publicos_for_fiesta_language(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-espectaculos-fiesta",
        nombre=f"Impuesto sobre Espectaculos Publicos {test_slug_prefix}",
        descripcion=(
            "Tramite tributario para eventos publicos, fiestas y espectaculos "
            "realizados dentro del municipio."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Donde se paga lo de la fiesta que voy a hacer"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert "espect" in principal_name
    assert "public" in principal_name


def test_consulta_matches_espectaculos_publicos_for_baile_con_orquesta_language(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-espectaculos-orquesta",
        nombre=f"Impuesto sobre Espectaculos Publicos {test_slug_prefix}",
        descripcion=(
            "Tramite tributario para espectaculos publicos, bailes, conciertos "
            "y presentaciones musicales en el municipio."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Permiso de la alcaldia para baile con orquesta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert "espect" in principal_name
    assert "public" in principal_name


def test_consulta_tolerates_typo_for_predial_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion del impuetso predial"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()


def test_consulta_tolerates_typo_for_vehicular_query(client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-vehicular-typo",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Gestion del impuesto vehicular para carros y motos dentro del catalogo tributario del asistente.",
        dependencia="Secretaria de transito y movilidad",
    )

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


def test_consulta_persists_log_entry_when_logging_is_enabled(client, admin_headers, test_slug_prefix) -> None:
    app.state.disable_consulta_logging = False
    question = "test-log-carro"

    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-vehicular-log",
        nombre=f"Impuesto vehicular {test_slug_prefix}",
        descripcion="Gestion del impuesto vehicular para carros y motos dentro del catalogo tributario del asistente.",
        dependencia="Secretaria de transito y movilidad",
    )

    try:
        response = client.post(
            "/api/consulta",
            json={"pregunta": question},
        )

        assert response.status_code == 200

        db = SessionLocal()
        try:
            log_entry = db.query(ConsultaLog).filter(ConsultaLog.pregunta == question).one_or_none()
            assert log_entry is not None
            assert log_entry.mensaje_estado == "Coincidencias semanticas encontradas"
            assert log_entry.origen_respuesta == "semantica"
            assert log_entry.tramite_principal_nombre is not None
            assert "vehicular" in log_entry.tramite_principal_nombre.lower()
            assert log_entry.resumen_respuesta
        finally:
            db.close()
    finally:
        app.state.disable_consulta_logging = True


def test_admin_can_list_recent_consulta_logs(client, admin_headers) -> None:
    app.state.disable_consulta_logging = False
    question = "test-log-impuestos"

    try:
        client.post(
            "/api/consulta",
            json={"pregunta": question},
        )

        response = client.get("/api/admin/consultas", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        matching_log = next((item for item in data if item["pregunta"] == question), None)
        assert matching_log is not None
        assert "resumen_respuesta" in matching_log
        assert "sugerencias" in matching_log
        assert "tramites_relacionados" in matching_log
    finally:
        app.state.disable_consulta_logging = True
