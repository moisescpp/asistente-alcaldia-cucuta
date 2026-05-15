import app.api.routes as routes_module
from app.database import SessionLocal
from app.models import Tramite
from app.services.admin_auth_service import create_admin_session_token


def build_payload(slug: str, **overrides) -> dict:
    payload = {
        "nombre": f"Test tramite {slug}",
        "slug": slug,
        "descripcion": (
            "Gestion tributaria temporal para validar la calidad semantica del "
            "asistente y la creacion administrativa con lenguaje ciudadano claro."
        ),
        "requisitos": (
            "Documento de identidad vigente, formulario completo y soporte del "
            "tramite solicitado."
        ),
        "costo": "Sin costo",
        "horario": "Lunes a viernes",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://example.com/tramite",
        "activo": True,
    }
    payload.update(overrides)
    return payload


def test_admin_session_rejects_invalid_pin(client) -> None:
    response = client.post("/api/admin/session", json={"pin": "000000"})

    assert response.status_code == 401
    assert "pin administrativo" in response.json()["detail"].lower()


def test_admin_session_returns_trial_ttl_metadata(client) -> None:
    response = client.post("/api/admin/session", json={"pin": routes_module.settings.admin_access_pin})

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"].count(".") == 2
    assert data["expires_in_seconds"] == 300
    assert data["expires_at"] > 0


def test_admin_session_rejects_default_credentials_in_production(client) -> None:
    original_env = routes_module.settings.app_env
    original_pin = routes_module.settings.admin_access_pin
    original_secret = routes_module.settings.admin_session_secret
    try:
        routes_module.settings.app_env = "production"
        routes_module.settings.admin_access_pin = "246810"
        routes_module.settings.admin_session_secret = "cucuta-admin-session-secret"

        response = client.post("/api/admin/session", json={"pin": "246810"})
    finally:
        routes_module.settings.app_env = original_env
        routes_module.settings.admin_access_pin = original_pin
        routes_module.settings.admin_session_secret = original_secret

    assert response.status_code == 503
    assert "credenciales seguras" in response.json()["detail"].lower()


def test_admin_session_status_confirms_active_private_access(client, admin_headers) -> None:
    response = client.get("/api/admin/session", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert 0 < data["expires_in_seconds"] <= 300
    assert data["expires_at"] > 0


def test_new_admin_session_invalidates_previous_access(client) -> None:
    first_response = client.post("/api/admin/session", json={"pin": routes_module.settings.admin_access_pin})
    assert first_response.status_code == 200
    first_token = first_response.json()["access_token"]

    second_response = client.post("/api/admin/session", json={"pin": routes_module.settings.admin_access_pin})
    assert second_response.status_code == 200

    stale_response = client.get(
        "/api/admin/session",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert stale_response.status_code == 401
    assert "otro dispositivo" in stale_response.json()["detail"].lower()


def test_admin_session_status_rejects_legacy_long_lived_token(client) -> None:
    original_ttl_minutes = routes_module.settings.admin_session_ttl_minutes
    try:
        routes_module.settings.admin_session_ttl_minutes = 600
        legacy_token, _, _, _ = create_admin_session_token()
        routes_module.settings.admin_session_ttl_minutes = 5

        response = client.get(
            "/api/admin/session",
            headers={"Authorization": f"Bearer {legacy_token}"},
        )
    finally:
        routes_module.settings.admin_session_ttl_minutes = original_ttl_minutes

    assert response.status_code == 401
    assert "expiro" in response.json()["detail"].lower()


def test_admin_endpoints_require_authenticated_session(client, test_slug_prefix) -> None:
    payload = build_payload(f"{test_slug_prefix}-locked")

    response = client.post("/api/admin/tramites", json=payload)

    assert response.status_code == 401
    assert "autenticarte" in response.json()["detail"].lower()


def test_create_tramite_returns_201_and_persists(client, admin_headers, test_slug_prefix) -> None:
    payload = build_payload(f"{test_slug_prefix}-create")

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == payload["nombre"]
    assert data["slug"] == payload["slug"]
    assert data["activo"] is True
    assert data["semantic_quality_score"] >= 70
    assert data["semantic_quality_level"] in {"estable", "fuerte"}
    assert data["semantic_scope_status"] == "tributario"
    assert data["semantic_recommended_action"]


def test_create_tramite_accepts_extended_procedure_fields(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-extended-fields",
        nombre=f"Test tramite campos extendidos {test_slug_prefix}",
        dirigido_a="Ciudadanos propietarios o responsables del tramite tributario.",
        pasos=(
            "Radicar los documentos en ventanilla unica o por la pagina web. "
            "Click Aqui para continuar con el seguimiento institucional."
        ),
        tiempo_estimado="Cinco dias habiles",
        medio_seguimiento="Pagina web oficial de la Alcaldia o ventanilla unica.",
        normatividad="Acuerdo municipal vigente y normas tributarias aplicables.",
        enlace_click_aqui="https://example.com/seguimiento-especifico",
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["dirigido_a"] == payload["dirigido_a"]
    assert data["pasos"] == payload["pasos"]
    assert data["tiempo_estimado"] == payload["tiempo_estimado"]
    assert data["medio_seguimiento"] == payload["medio_seguimiento"]
    assert data["normatividad"] == payload["normatividad"]
    assert data["enlace_click_aqui"] == payload["enlace_click_aqui"]


def test_update_tramite_returns_updated_payload(client, admin_headers, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-update")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()

    update_payload = {
        "costo": "Costo sujeto a liquidacion vigente",
        "horario": "Jornada continua",
    }

    response = client.put(f"/api/admin/tramites/{created['id']}", json=update_payload, headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["costo"] == update_payload["costo"]
    assert data["horario"] == update_payload["horario"]
    assert data["semantic_scope_status"] == "tributario"


def test_update_tramite_accepts_long_estimated_time_and_click_link(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-long-time-update")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()
    long_time = (
        "El tiempo puede variar segun el volumen de solicitudes recibidas por la entidad; "
        "se recomienda consultar periodicamente el estado de la radicacion por el canal oficial."
    )
    click_link = "https://example.com/radicacion-especifica"

    response = client.put(
        f"/api/admin/tramites/{created['id']}",
        json={
            "tiempo_estimado": long_time,
            "pasos": "Radicar documentos en la plataforma institucional. Click Aqui para abrir el canal de seguimiento.",
            "enlace_click_aqui": click_link,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tiempo_estimado"] == long_time
    assert data["enlace_click_aqui"] == click_link


def test_create_tramite_rejects_generic_description(client, admin_headers, test_slug_prefix) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-generic-desc",
        descripcion="Consulta orientativa del tramite.",
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert "descripcion" in response.json()["detail"].lower()


def test_create_tramite_rejects_short_requirements(client, admin_headers, test_slug_prefix) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-short-req",
        requisitos="Documento.",
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert "requisitos" in response.json()["detail"].lower()


def test_create_tramite_normalizes_dependency_spacing(client, admin_headers, test_slug_prefix) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-dep-normalize",
        dependencia="  Secretaria   de Hacienda   -   Rentas e Impuestos  ",
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["dependencia"] == "Secretaria de Hacienda - Rentas e Impuestos"


def test_update_tramite_normalizes_dependency_spacing(client, admin_headers, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-dep-update")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()

    response = client.put(
        f"/api/admin/tramites/{created['id']}",
        json={"dependencia": "  Secretaria   de Hacienda   -   Rentas e Impuestos  "},
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dependencia"] == "Secretaria de Hacienda - Rentas e Impuestos"


def test_delete_tramite_marks_record_inactive_and_hides_from_public_list(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-delete")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)

    assert delete_response.status_code == 200
    assert delete_response.json()["activo"] is False

    list_response = client.get("/api/tramites")
    listed_ids = [tramite["id"] for tramite in list_response.json()]
    assert created["id"] not in listed_ids


def test_admin_can_list_inactive_tramites(client, admin_headers, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-inactive-list")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()
    client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)

    response = client.get("/api/admin/tramites/desactivados", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    inactive_ids = [tramite["id"] for tramite in data]
    assert created["id"] in inactive_ids


def test_admin_can_reactivate_inactive_tramite(client, admin_headers, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-reactivar-directo")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()
    client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)

    reactivate_response = client.post(
        f"/api/admin/tramites/{created['id']}/reactivar",
        headers=admin_headers,
    )

    assert reactivate_response.status_code == 200
    reactivated = reactivate_response.json()
    assert reactivated["activo"] is True

    public_list_response = client.get("/api/tramites")
    listed_ids = [tramite["id"] for tramite in public_list_response.json()]
    assert created["id"] in listed_ids


def test_create_tramite_reactivates_existing_inactive_record(client, admin_headers, test_slug_prefix) -> None:
    slug = f"{test_slug_prefix}-reactivate"
    create_payload = build_payload(slug, nombre=f"Test tramite reactivate {slug}")
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)
    assert delete_response.status_code == 200

    recreated_payload = build_payload(
        slug,
        nombre=create_payload["nombre"],
        descripcion=(
            "Descripcion reactivada con contexto ciudadano suficiente para validar "
            "la reactivacion administrativa del tramite tributario."
        ),
    )
    recreate_response = client.post("/api/admin/tramites", json=recreated_payload, headers=admin_headers)

    assert recreate_response.status_code == 201
    recreated = recreate_response.json()
    assert recreated["id"] == created["id"]
    assert recreated["activo"] is True
    assert recreated["descripcion"] == recreated_payload["descripcion"]


def test_create_tramite_returns_409_for_active_duplicate_name(client, admin_headers, test_slug_prefix) -> None:
    payload = build_payload(f"{test_slug_prefix}-dup", nombre=f"Test tramite duplicate {test_slug_prefix}")
    first_response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)
    assert first_response.status_code == 201

    duplicate_payload = build_payload(f"{test_slug_prefix}-dup-2", nombre=payload["nombre"])
    duplicate_response = client.post("/api/admin/tramites", json=duplicate_payload, headers=admin_headers)

    assert duplicate_response.status_code == 409
    assert "nombre" in duplicate_response.json()["detail"]


def test_update_tramite_returns_409_for_duplicate_slug(client, admin_headers, test_slug_prefix) -> None:
    first_payload = build_payload(f"{test_slug_prefix}-slug-a")
    second_payload = build_payload(f"{test_slug_prefix}-slug-b")

    first = client.post("/api/admin/tramites", json=first_payload, headers=admin_headers).json()
    second = client.post("/api/admin/tramites", json=second_payload, headers=admin_headers).json()

    response = client.put(
        f"/api/admin/tramites/{second['id']}",
        json={"slug": first["slug"]},
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert "slug" in response.json()["detail"]


def test_reactivated_tramite_is_persisted_as_active_in_database(client, admin_headers, test_slug_prefix) -> None:
    slug = f"{test_slug_prefix}-db-reactivate"
    payload = build_payload(slug, nombre=f"Test tramite db {slug}")
    created = client.post("/api/admin/tramites", json=payload, headers=admin_headers).json()
    client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)
    client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    db = SessionLocal()
    try:
        record = db.get(Tramite, created["id"])
        assert record is not None
        assert record.activo is True
        assert record.slug == slug
    finally:
        db.close()


def test_create_tramite_attempts_embedding_sync(
    client,
    admin_headers,
    test_slug_prefix,
    monkeypatch,
) -> None:
    payload = build_payload(f"{test_slug_prefix}-embedding")
    sync_calls: list[str] = []

    def fake_update_tramite_embedding(db, tramite):
        sync_calls.append(tramite.slug)
        return tramite

    monkeypatch.setattr(
        routes_module,
        "update_tramite_embedding",
        fake_update_tramite_embedding,
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 201
    assert sync_calls == [payload["slug"]]


def test_create_tramite_still_succeeds_if_embedding_sync_fails(
    client,
    admin_headers,
    test_slug_prefix,
    monkeypatch,
) -> None:
    payload = build_payload(f"{test_slug_prefix}-embedding-fail")

    def fake_update_tramite_embedding(db, tramite):
        raise RuntimeError("Fallo simulado de embeddings")

    monkeypatch.setattr(
        routes_module,
        "update_tramite_embedding",
        fake_update_tramite_embedding,
    )

    response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == payload["slug"]


def test_created_tramite_is_immediately_available_for_consulta(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-consulta-create",
        nombre=f"Certificado tributario especial {test_slug_prefix}",
        descripcion=(
            "Emision de certificado tributario especial para validar la "
            "integracion entre administracion y consulta."
        ),
    )

    created_response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)
    created = created_response.json()

    consulta_response = client.post(
        "/api/consulta",
        json={"pregunta": payload["nombre"]},
    )

    assert created_response.status_code == 201
    assert consulta_response.status_code == 200
    consulta = consulta_response.json()
    assert consulta["tramite_principal"] is not None
    assert consulta["tramite_principal"]["id"] == created["id"]
    assert payload["nombre"] in consulta["respuesta"]


def test_created_tramite_can_be_found_by_plain_language_from_registered_content(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-consulta-plain-language",
        nombre=f"Certificado tributario de residencia {test_slug_prefix}",
        descripcion=(
            "Orientacion para ciudadanos que necesitan demostrar residencia fiscal "
            "municipal en una solicitud tributaria."
        ),
        requisitos=(
            "Documento de identidad vigente, recibo de servicio publico del lugar "
            "de residencia y solicitud firmada por el ciudadano."
        ),
    )

    created_response = client.post("/api/admin/tramites", json=payload, headers=admin_headers)
    created = created_response.json()

    consulta_response = client.post(
        "/api/consulta",
        json={"pregunta": "necesito demostrar residencia fiscal municipal con un recibo publico"},
    )

    assert created_response.status_code == 201
    assert consulta_response.status_code == 200
    consulta = consulta_response.json()
    assert consulta["tramite_principal"] is not None
    assert consulta["tramite_principal"]["id"] == created["id"]
    assert "residencia fiscal municipal" in consulta["respuesta"].lower()


def test_updated_tramite_is_reflected_in_consulta_results(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    create_payload = build_payload(
        f"{test_slug_prefix}-consulta-update",
        nombre=f"Liquidacion temporal {test_slug_prefix}",
        descripcion=(
            "Descripcion inicial con contexto tributario suficiente para validar "
            "la actualizacion administrativa del tramite."
        ),
    )
    created = client.post("/api/admin/tramites", json=create_payload, headers=admin_headers).json()

    update_payload = {
        "nombre": f"Liquidacion definitiva {test_slug_prefix}",
        "descripcion": (
            "Descripcion actualizada con detalle ciudadano suficiente para que la "
            "consulta final recupere el tramite correcto."
        ),
    }
    update_response = client.put(
        f"/api/admin/tramites/{created['id']}",
        json=update_payload,
        headers=admin_headers,
    )
    consulta_response = client.post(
        "/api/consulta",
        json={"pregunta": update_payload["nombre"]},
    )

    assert update_response.status_code == 200
    assert consulta_response.status_code == 200
    consulta = consulta_response.json()
    assert consulta["tramite_principal"] is not None
    assert consulta["tramite_principal"]["id"] == created["id"]
    assert consulta["tramite_principal"]["nombre"] == update_payload["nombre"]
    assert consulta["tramite_principal"]["descripcion"] == update_payload["descripcion"]


def test_deactivated_tramite_is_no_longer_available_for_consulta(
    client,
    admin_headers,
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-consulta-delete",
        nombre=f"Recibo tributario temporal {test_slug_prefix}",
        descripcion=(
            "Gestion tributaria temporal con detalle suficiente para validar que la "
            "desactivacion quite el tramite de la consulta ciudadana."
        ),
    )
    created = client.post("/api/admin/tramites", json=payload, headers=admin_headers).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}", headers=admin_headers)
    consulta_response = client.post(
        "/api/consulta",
        json={"pregunta": payload["nombre"]},
    )

    assert delete_response.status_code == 200
    assert consulta_response.status_code == 200
    consulta = consulta_response.json()
    principal_id = consulta["tramite_principal"]["id"] if consulta["tramite_principal"] else None
    related_ids = [tramite["id"] for tramite in consulta["tramites_relacionados"]]

    assert created["id"] != principal_id
    assert created["id"] not in related_ids
