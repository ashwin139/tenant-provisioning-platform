import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    """A fresh API with its own SQLite file per test."""
    app = create_app(db_path=str(tmp_path / "test.db"), step_delay_seconds=0)
    with TestClient(app) as c:
        yield c
