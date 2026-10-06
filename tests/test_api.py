"""Phase 2: API contract — create, get, and rejection cases."""

ACME = {"name": "acme", "region": "ca-central-1", "plan": "standard", "tenant_model": "pooled"}


def test_create_tenant_is_accepted(client):
    r = client.post("/api/v1/tenants", json=ACME)
    assert r.status_code == 202
    body = r.json()
    assert body["tenant_id"]
    assert body["name"] == "acme"
    assert body["status"] == "REQUESTED"
    assert [s["name"] for s in body["steps"]] == [
        "validate", "provision_data", "configure", "deploy", "verify",
    ]
    assert all(s["status"] == "PENDING" for s in body["steps"])
    assert body["created_at"] and body["ready_at"] is None


def test_get_tenant_returns_created_tenant(client):
    tenant_id = client.post("/api/v1/tenants", json=ACME).json()["tenant_id"]
    r = client.get(f"/api/v1/tenants/{tenant_id}")
    assert r.status_code == 200
    assert r.json()["tenant_id"] == tenant_id


def test_get_unknown_tenant_is_404(client):
    r = client.get("/api/v1/tenants/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "tenant_not_found"


def test_siloed_tenancy_is_rejected_as_unsupported(client):
    r = client.post("/api/v1/tenants", json={**ACME, "tenant_model": "siloed"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_tenant_model"


def test_duplicate_name_is_conflict(client):
    assert client.post("/api/v1/tenants", json=ACME).status_code == 202
    r = client.post("/api/v1/tenants", json=ACME)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_tenant_name"


def test_invalid_name_is_validation_error(client):
    r = client.post("/api/v1/tenants", json={**ACME, "name": "Not Valid!"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["details"][0]["field"] == "name"
