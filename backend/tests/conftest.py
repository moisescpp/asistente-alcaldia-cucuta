import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.database import SessionLocal
from app.models import Tramite


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_slug_prefix() -> str:
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def cleanup_test_tramites() -> None:
    yield

    db = SessionLocal()
    try:
        db.execute(delete(Tramite).where(Tramite.slug.like("test-%")))
        db.commit()
    finally:
        db.close()
