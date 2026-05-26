import unicodedata

import pytest

from app.database import SessionLocal
from app.main import app
from app.models import ConsultaLog, Tramite
from app.services import consulta_service
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


def test_success_response_uses_local_intro_by_default(monkeypatch) -> None:
    monkeypatch.setattr(consulta_service.settings, "enable_rag_intro", False)

    def fail_if_called(**_kwargs):
        raise AssertionError("La introduccion RAG no debe ejecutarse por defecto.")

    monkeypatch.setattr(consulta_service, "generate_rag_response", fail_if_called)

    tramite = Tramite(
        id=101,
        nombre="Impuesto predial unificado",
        slug="impuesto-predial-unificado",
        descripcion="Consulta del impuesto predial municipal.",
        requisitos="Documento de identidad y referencia catastral.",
        costo="Sin costo",
        horario="Lunes a viernes",
        dependencia="Secretaria de Hacienda - Rentas e Impuestos",
        fuente_url="https://example.com/predial",
        activo=True,
    )

    response = consulta_service._build_success_response(
        pregunta="Necesito informacion sobre predial",
        tramites=[tramite],
        message_status="Coincidencias encontradas",
    )

    assert response.tramite_principal is not None
    assert response.tramite_principal.nombre == "Impuesto predial unificado"
    assert "Tramite principal: Impuesto predial unificado" in response.respuesta


def test_clear_textual_query_skips_semantic_embedding(monkeypatch, client, admin_headers, test_slug_prefix) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-predial-fast",
        nombre=f"Impuesto predial rapido {test_slug_prefix}",
        descripcion=(
            "Consulta del impuesto predial municipal para casas, predios e inmuebles "
            "registrados dentro de la jurisdiccion local."
        ),
        requisitos=(
            "Documento de identidad vigente, referencia catastral y datos basicos "
            "del inmueble consultado."
        ),
    )

    def fail_if_called(_text):
        raise AssertionError("La ruta textual confiable no debe generar embeddings.")

    monkeypatch.setattr(consulta_service, "generate_embedding", fail_if_called)

    response = client.post(
        "/api/consulta",
        json={"pregunta": f"requisitos impuesto predial rapido {test_slug_prefix}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial rapido" in data["tramite_principal"]["nombre"].lower()


def test_generic_clarification_uses_textual_candidates_before_embedding(
    monkeypatch,
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    for suffix in ("predial", "industria", "alumbrado"):
        create_test_tramite(
            client,
            admin_headers,
            f"{test_slug_prefix}-impuesto-{suffix}",
            nombre=f"Impuesto municipal {suffix} {test_slug_prefix}",
            descripcion=(
                "Ficha tributaria relacionada con impuestos municipales y gestiones "
                "de orientacion ciudadana ante la administracion local."
            ),
            requisitos=(
                "Documento de identidad vigente y soporte basico de la solicitud "
                "ciudadana correspondiente."
            ),
        )

    def fail_if_called(_text):
        raise AssertionError("La aclaracion textual suficiente no debe generar embeddings.")

    monkeypatch.setattr(consulta_service, "generate_embedding", fail_if_called)

    response = client.post("/api/consulta", json={"pregunta": "impuestos"})

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert data["total_resultados"] >= 3


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
        f"{test_slug_prefix}-predial-noemb",
        nombre=f"Impuesto predial sin embedding {test_slug_prefix}",
        descripcion="Gestion del impuesto predial municipal para casas, lotes y predios registrados en la ciudad.",
        dependencia="Secretaria de Hacienda - Rentas e Impuestos",
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
        json={"pregunta": "impuesto predial sin embedding"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()


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


def test_consulta_understands_house_context_phrase(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "quiero saber lo de la casa"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()


@pytest.mark.parametrize(
    ("question", "expected_terms"),
    [
        ("necesito registrar mi negocio", ("industria", "comercio")),
        ("quiero cambiar datos de industria y comercio", ("modificacion",)),
        ("voy a hacer un concierto con boletas", ("espect",)),
        ("me cobraron de mas y quiero devolucion", ("devolucion", "compensacion")),
        ("necesito sacar paz y salvo", ("paz", "salvo")),
        ("paz y salbo municipal", ("paz", "salvo")),
        ("impuesto sobre iluminacion publica", ("alumbrado",)),
        ("necesito saber sobre lo de la luz", ("alumbrado",)),
    ],
)
def test_consulta_handles_core_revenue_tax_catalog_intentions(
    client,
    question,
    expected_terms,
) -> None:
    response = client.post("/api/consulta", json={"pregunta": question})

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert any(term in principal_name for term in expected_terms)


@pytest.mark.parametrize(
    "question",
    [
        "quiero actualizar el sisben por cambio de direccion",
        "se me perdio la tarjeta del carro",
        "impuesto vehicular",
    ],
)
def test_consulta_rejects_out_of_scope_catalog_intentions(client, question) -> None:
    response = client.post("/api/consulta", json={"pregunta": question})

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is None
    assert data["mensaje_estado"] in {
        "Sin coincidencias en la base actual",
        "Consulta demasiado general",
    }


def test_consulta_understands_business_closure_language(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-cancelacion-contribuyentes",
        nombre=f"Cancelacion del registro de contribuyentes {test_slug_prefix}",
        descripcion=(
            "Tramite para cancelar o cerrar el registro de contribuyentes de "
            "industria y comercio cuando cesa la actividad economica."
        ),
        requisitos=(
            "Solicitud formal, documento de identidad y soporte del cierre o "
            "cese de actividades del establecimiento."
        ),
    )

    response = client.post(
        "/api/consulta",
        json={"pregunta": "quiero cerrar mi negocio y cancelar industria y comercio"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    principal_name = normalize_assert_text(data["tramite_principal"]["nombre"])
    assert "cancelacion" in principal_name


def test_consulta_rejects_out_of_scope_car_language(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "carro"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is None
    assert data["mensaje_estado"] in {
        "Sin coincidencias en la base actual",
        "Consulta demasiado general",
    }


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


def test_consulta_rejects_out_of_scope_transit_language(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion de transito sobre impuesto vehicular"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is None
    assert data["mensaje_estado"] in {
        "Sin coincidencias en la base actual",
        "Consulta demasiado general",
    }


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


def test_consulta_rejects_generic_multiword_query_even_with_typos(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "informacion de impuetos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1
    assert len(data["tramites_relacionados"]) >= 1


def test_consulta_rejects_article_prefixed_generic_tax_query_with_typo(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "los inpuestos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1
    assert all(
        "sisben" not in (tramite["nombre"] or "").lower()
        for tramite in data["tramites_relacionados"]
    )


def test_generic_tax_typo_clarification_does_not_surface_unrelated_sisben_candidate(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-predgen",
        nombre=f"Impuesto predial {test_slug_prefix}",
        descripcion=(
            "Consulta del impuesto predial municipal para casas, lotes y predios "
            "con contexto suficiente para validar una aclaracion ciudadana general."
        ),
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-devgen",
        nombre=f"Devolucion de pagos {test_slug_prefix}",
        descripcion=(
            "Devolucion y compensacion de pagos en exceso de impuestos municipales "
            "con lenguaje ciudadano suficiente para la validacion de pruebas."
        ),
    )
    db = SessionLocal()
    try:
        tramite = Tramite(
            nombre=f"Actualizacion SISBEN {test_slug_prefix}",
            slug=f"{test_slug_prefix}-sisgen",
            descripcion=(
                "Actualizacion de datos del SISBEN para hogares registrados con "
                "informacion suficiente para diferenciarlo del catalogo tributario."
            ),
            requisitos="Documento de identidad, ficha SISBEN y soporte del cambio reportado.",
            costo="Sin costo",
            horario="Lunes a viernes",
            dependencia="Departamento Administrativo de Planeacion",
            fuente_url="https://example.com/sisben-prueba",
            activo=True,
        )
        db.add(tramite)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/consulta",
        json={"pregunta": "los inpuestos"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert all(
        "sisben" not in (tramite["nombre"] or "").lower()
        for tramite in data["tramites_relacionados"]
    )


def test_consulta_rejects_generic_payment_phrase_without_specific_context(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "ayda con pagoss"},
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
    assert data["mensaje_estado"] == "Consulta demasiado general"
    assert data["tramite_principal"] is None
    assert len(data["sugerencias"]) >= 1
    assert len(data["tramites_relacionados"]) >= 1


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


def test_consulta_rejects_out_of_scope_unregistered_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "Cuanto cuesta renovar el pasaporte colombiano?"},
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


def test_consulta_prioritizes_common_citizen_intents_over_related_industria_records(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-registro-comercio",
        nombre=f"Registro de contribuyentes del impuesto de industria y comercio {test_slug_prefix}",
        descripcion="Inscripcion inicial de personas naturales o juridicas que abren negocio o actividad comercial.",
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-cancelacion-comercio",
        nombre=f"Cancelacion del registro de contribuyentes del impuesto de industria y comercio {test_slug_prefix}",
        descripcion=(
            "Cancelacion o cese de actividades para contribuyentes que cerraron su negocio "
            "y necesitan retirar el registro de industria y comercio ante la entidad."
        ),
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-correccion-comercio",
        nombre=f"Correccion de año y/o periodo gravable en declaraciones de industria y comercio {test_slug_prefix}",
        descripcion=(
            "Correccion de errores e inconsistencias en declaraciones de industria y comercio "
            "cuando el contribuyente necesita ajustar el año o periodo gravable reportado."
        ),
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-paz-salvo",
        nombre=f"Generacion de Paz y Salvo {test_slug_prefix}",
        descripcion="Certificado para consultar si el contribuyente esta al dia con sus obligaciones tributarias.",
    )
    create_test_tramite(
        client,
        admin_headers,
        f"{test_slug_prefix}-espectaculos",
        nombre=f"Impuesto sobre Espectaculos Publicos {test_slug_prefix}",
        descripcion=(
            "Impuesto aplicable a eventos, conciertos, actividades con publico, "
            "fiestas con entrada, espectaculos publicos y venta de boleteria."
        ),
    )

    cases = [
        ("Voy a abrir un negocio.", "registro"),
        ("Quiero sacar el registro ICA.", "registro"),
        ("¿Dónde inscribo mi actividad comercial?", "registro"),
        ("Necesito registrar mi comercio.", "registro"),
        ("Quiero legalizar mi negocio ante rentas.", "registro"),
        ("Quiero informacion para una actividad con publico", "espectaculos"),
        ("Quiero saber si tengo deudas con la Alcaldía", "paz y salvo"),
        ("Necesito el certificado para vender una casa.", "paz y salvo"),
        ("Quiero cerrar mi negocio.", "cancelacion"),
        ("Tengo un error en la declaracion de industria y comercio.", "correccion"),
    ]

    for pregunta, expected_name in cases:
        response = client.post("/api/consulta", json={"pregunta": pregunta})

        assert response.status_code == 200
        data = response.json()
        assert data["tramite_principal"] is not None, pregunta
        assert expected_name in normalize_assert_text(data["tramite_principal"]["nombre"]), pregunta


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


def test_consulta_prioritizes_predial_name_over_noisy_related_aliases(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    predial_payload = build_payload(
        f"{test_slug_prefix}-predial-noise",
        nombre=f"Impuesto predial extremo {test_slug_prefix}",
        descripcion=(
            "Consulta del impuesto predial municipal para predios, casas y lotes "
            "registrados en la jurisdiccion local."
        ),
        requisitos="Referencia catastral vigente y documento de identidad del propietario.",
    )
    refund_payload = build_payload(
        f"{test_slug_prefix}-refund-noise",
        nombre=f"Devolucion tributaria extrema {test_slug_prefix}",
        descripcion=(
            "Solicitud para revisar pagos en exceso, compensaciones y saldos a favor "
            "asociados a obligaciones tributarias."
        ),
        requisitos="Soporte de pago, solicitud firmada y certificacion bancaria vigente.",
    )

    client.post("/api/admin/tramites", json=predial_payload, headers=admin_headers)
    refund = client.post("/api/admin/tramites", json=refund_payload, headers=admin_headers).json()

    db = SessionLocal()
    try:
        noisy_record = db.get(Tramite, refund["id"])
        assert noisy_record is not None
        noisy_record.alias_ciudadanos = (
            "predial lo o devolver\n"
            "a predial y lo\n"
            "informacion sobre impuesto predial para devoluciones"
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/consulta",
        json={"pregunta": "Necesito informacion sobre impuesto predial"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is not None
    assert "predial" in data["tramite_principal"]["nombre"].lower()
    assert data["tramite_principal"]["id"] != refund["id"]


def test_deleted_then_recreated_tramite_is_the_only_consultable_version(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    slug = f"{test_slug_prefix}-predial-recreate"
    payload = build_payload(
        slug,
        nombre=f"Impuesto predial recreado {test_slug_prefix}",
        descripcion=(
            "Consulta del impuesto predial recreado para validar eliminacion logica, "
            "reactivacion y disponibilidad inmediata al ciudadano."
        ),
        requisitos="Referencia catastral, documento de identidad y soporte del predio.",
    )
    created = client.post("/api/admin/tramites", json=payload, headers=admin_headers).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)
    deleted_query = client.post("/api/consulta", json={"pregunta": payload["nombre"]})

    recreated_payload = {
        **payload,
        "descripcion": (
            "Ficha recreada del impuesto predial con datos vigentes para responder "
            "la consulta ciudadana despues de una reactivacion administrativa."
        ),
    }
    recreate_response = client.post(
        "/api/admin/tramites",
        json=recreated_payload,
        headers=admin_headers,
    )
    recreated_query = client.post("/api/consulta", json={"pregunta": payload["nombre"]})

    assert delete_response.status_code == 200
    deleted_data = deleted_query.json()
    deleted_ids = [
        tramite["id"]
        for tramite in [
            *(deleted_data["tramites_relacionados"] or []),
            *([deleted_data["tramite_principal"]] if deleted_data["tramite_principal"] else []),
        ]
    ]
    assert created["id"] not in deleted_ids

    assert recreate_response.status_code == 201
    recreated = recreate_response.json()
    assert recreated["id"] == created["id"]
    assert recreated["activo"] is True

    recreated_data = recreated_query.json()
    assert recreated_data["tramite_principal"] is not None
    assert recreated_data["tramite_principal"]["id"] == created["id"]
    assert "Ficha recreada" in recreated_data["tramite_principal"]["descripcion"]


def test_consulta_rejects_typo_for_out_of_scope_vehicular_query(client) -> None:
    response = client.post(
        "/api/consulta",
        json={"pregunta": "impuesto vehivular"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tramite_principal"] is None
    assert data["mensaje_estado"] in {
        "Sin coincidencias en la base actual",
        "Consulta demasiado general",
    }


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
    question = "test-log-predial"

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
            assert log_entry.mensaje_estado in {
                "Coincidencias encontradas",
                "Coincidencias semanticas encontradas",
            }
            assert log_entry.origen_respuesta in {"textual", "semantica"}
            assert log_entry.tramite_principal_nombre is not None
            assert "predial" in log_entry.tramite_principal_nombre.lower()
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
        assert matching_log["response_time_ms"] is not None
        assert matching_log["response_time_ms"] >= 0
    finally:
        app.state.disable_consulta_logging = True
