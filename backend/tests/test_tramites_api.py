import app.api.routes as routes_module
from app.database import SessionLocal
from app.models import Tramite


def build_payload(slug: str, **overrides) -> dict:
    payload = {
        "nombre": f"Test tramite {slug}",
        "slug": slug,
        "descripcion": "Tramite de prueba para validar endpoints.",
        "requisitos": "Documento de identidad.",
        "costo": "Sin costo",
        "horario": "Lunes a viernes",
        "dependencia": "Secretaria de Hacienda - Rentas e Impuestos",
        "fuente_url": "https://example.com/tramite",
        "activo": True,
    }
    payload.update(overrides)
    return payload


def test_create_tramite_returns_201_and_persists(client, test_slug_prefix) -> None:
    payload = build_payload(f"{test_slug_prefix}-create")

    response = client.post("/api/admin/tramites", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == payload["nombre"]
    assert data["slug"] == payload["slug"]
    assert data["activo"] is True


def test_update_tramite_returns_updated_payload(client, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-update")
    created = client.post("/api/admin/tramites", json=create_payload).json()

    update_payload = {
        "costo": "Costo sujeto a liquidacion vigente",
        "horario": "Jornada continua",
    }

    response = client.put(f"/api/admin/tramites/{created['id']}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["costo"] == update_payload["costo"]
    assert data["horario"] == update_payload["horario"]


def test_create_tramite_normalizes_dependency_spacing(client, test_slug_prefix) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-dep-normalize",
        dependencia="  Secretaria   de Hacienda   -   Rentas e Impuestos  ",
    )

    response = client.post("/api/admin/tramites", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["dependencia"] == "Secretaria de Hacienda - Rentas e Impuestos"


def test_update_tramite_normalizes_dependency_spacing(client, test_slug_prefix) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-dep-update")
    created = client.post("/api/admin/tramites", json=create_payload).json()

    response = client.put(
        f"/api/admin/tramites/{created['id']}",
        json={"dependencia": "  Secretaria   de Hacienda   -   Rentas e Impuestos  "},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dependencia"] == "Secretaria de Hacienda - Rentas e Impuestos"


def test_delete_tramite_marks_record_inactive_and_hides_from_public_list(
    client,
    test_slug_prefix,
) -> None:
    create_payload = build_payload(f"{test_slug_prefix}-delete")
    created = client.post("/api/admin/tramites", json=create_payload).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}")

    assert delete_response.status_code == 200
    assert delete_response.json()["activo"] is False

    list_response = client.get("/api/tramites")
    listed_ids = [tramite["id"] for tramite in list_response.json()]
    assert created["id"] not in listed_ids


def test_create_tramite_reactivates_existing_inactive_record(client, test_slug_prefix) -> None:
    slug = f"{test_slug_prefix}-reactivate"
    create_payload = build_payload(slug, nombre=f"Test tramite reactivate {slug}")
    created = client.post("/api/admin/tramites", json=create_payload).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}")
    assert delete_response.status_code == 200

    recreated_payload = build_payload(
        slug,
        nombre=create_payload["nombre"],
        descripcion="Descripcion reactivada",
    )
    recreate_response = client.post("/api/admin/tramites", json=recreated_payload)

    assert recreate_response.status_code == 201
    recreated = recreate_response.json()
    assert recreated["id"] == created["id"]
    assert recreated["activo"] is True
    assert recreated["descripcion"] == "Descripcion reactivada"


def test_create_tramite_returns_409_for_active_duplicate_name(client, test_slug_prefix) -> None:
    payload = build_payload(f"{test_slug_prefix}-dup", nombre=f"Test tramite duplicate {test_slug_prefix}")
    first_response = client.post("/api/admin/tramites", json=payload)
    assert first_response.status_code == 201

    duplicate_payload = build_payload(f"{test_slug_prefix}-dup-2", nombre=payload["nombre"])
    duplicate_response = client.post("/api/admin/tramites", json=duplicate_payload)

    assert duplicate_response.status_code == 409
    assert "nombre" in duplicate_response.json()["detail"]


def test_update_tramite_returns_409_for_duplicate_slug(client, test_slug_prefix) -> None:
    first_payload = build_payload(f"{test_slug_prefix}-slug-a")
    second_payload = build_payload(f"{test_slug_prefix}-slug-b")

    first = client.post("/api/admin/tramites", json=first_payload).json()
    second = client.post("/api/admin/tramites", json=second_payload).json()

    response = client.put(
        f"/api/admin/tramites/{second['id']}",
        json={"slug": first["slug"]},
    )

    assert response.status_code == 409
    assert "slug" in response.json()["detail"]


def test_reactivated_tramite_is_persisted_as_active_in_database(client, test_slug_prefix) -> None:
    slug = f"{test_slug_prefix}-db-reactivate"
    payload = build_payload(slug, nombre=f"Test tramite db {slug}")
    created = client.post("/api/admin/tramites", json=payload).json()
    client.delete(f"/api/admin/tramites/{created['id']}")
    client.post("/api/admin/tramites", json=payload)

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

    response = client.post("/api/admin/tramites", json=payload)

    assert response.status_code == 201
    assert sync_calls == [payload["slug"]]


def test_create_tramite_still_succeeds_if_embedding_sync_fails(
    client,
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

    response = client.post("/api/admin/tramites", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == payload["slug"]


def test_created_tramite_is_immediately_available_for_consulta(
    client,
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

    created_response = client.post("/api/admin/tramites", json=payload)
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


def test_updated_tramite_is_reflected_in_consulta_results(
    client,
    test_slug_prefix,
) -> None:
    create_payload = build_payload(
        f"{test_slug_prefix}-consulta-update",
        nombre=f"Liquidacion temporal {test_slug_prefix}",
        descripcion="Descripcion inicial para validar la actualizacion.",
    )
    created = client.post("/api/admin/tramites", json=create_payload).json()

    update_payload = {
        "nombre": f"Liquidacion definitiva {test_slug_prefix}",
        "descripcion": "Descripcion actualizada para validar la consulta final.",
    }
    update_response = client.put(
        f"/api/admin/tramites/{created['id']}",
        json=update_payload,
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
    test_slug_prefix,
) -> None:
    payload = build_payload(
        f"{test_slug_prefix}-consulta-delete",
        nombre=f"Recibo tributario temporal {test_slug_prefix}",
        descripcion="Tramite temporal para validar desactivacion en consulta.",
    )
    created = client.post("/api/admin/tramites", json=payload).json()

    delete_response = client.delete(f"/api/admin/tramites/{created['id']}")
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
