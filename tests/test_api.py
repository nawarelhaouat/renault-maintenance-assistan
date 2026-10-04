from app import api
from fastapi.testclient import TestClient


def test_health_needs_no_dependency():
    assert TestClient(api.app).get("/health").json() == {"status": "ok"}


def test_api_key_is_enforced(monkeypatch):
    monkeypatch.setattr(api, "API_KEY", "secret")
    client = TestClient(api.app)
    assert client.get("/machines").status_code == 401
    assert client.get("/machines", headers={"X-API-Key": "wrong"}).status_code == 401