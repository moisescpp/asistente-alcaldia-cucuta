import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.core.config import settings
from app.database import SessionLocal
from app.models import ConsultaLog, Tramite


@pytest.fixture
def client() -> TestClient:
    app.state.disable_consulta_logging = True
    return TestClient(app)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/session",
        json={"pin": settings.admin_access_pin},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_slug_prefix() -> str:
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def cleanup_test_tramites() -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(Tramite).where(
                or_(
                    Tramite.slug.like("test-%"),
                    Tramite.slug.like("%test-%"),
                    Tramite.nombre.like("Test %"),
                    Tramite.nombre.like("%test-%"),
                ),
            ),
        )
        db.execute(delete(ConsultaLog).where(ConsultaLog.pregunta.like("test-%")))
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        db.execute(
            delete(Tramite).where(
                or_(
                    Tramite.slug.like("test-%"),
                    Tramite.slug.like("%test-%"),
                    Tramite.nombre.like("Test %"),
                    Tramite.nombre.like("%test-%"),
                ),
            ),
        )
        db.execute(delete(ConsultaLog).where(ConsultaLog.pregunta.like("test-%")))
        db.commit()
    finally:
        db.close()
