from fastapi.testclient import TestClient

import app.api as api


def test_health_needs_no_dependency():
    assert TestClient(api.app).get("/health").json() == {"status": "ok"}


def test_protected_routes_require_a_token():
    client = TestClient(api.app)
    for path in ("/auth/me", "/machines", "/conversations", "/dashboard/summary"):
        assert client.get(path).status_code == 401
    assert client.post("/chat", json={"question": "test"}).status_code == 401