"""Phase 5: retry resumes from the failed step without repeating completed work."""
from app.models import StepName, StepStatus, TenantStatus

STEPS = ["validate", "provision_data", "configure", "deploy", "verify"]


def create(client, name="globex", **extra):
    body = {"name": name, "region": "ca-central-1", "plan": "standard", **extra}
    r = client.post("/api/v1/tenants", json=body)
    assert r.status_code == 202, r.text
    return client.get(f"/api/v1/tenants/{r.json()['tenant_id']}").json()


def retry(client, tenant_id):
    return client.post(f"/api/v1/tenants/{tenant_id}/retry")


def get(client, tenant_id):
    return client.get(f"/api/v1/tenants/{tenant_id}").json()


def steps(t):
    return {s["name"]: s for s in t["steps"]}


def test_failed_tenant_retries_to_ready(client):
    failed = create(client, fail_step="deploy")
    assert failed["status"] == "FAILED"

    r = retry(client, failed["tenant_id"])
    assert r.status_code == 202
    t = get(client, failed["tenant_id"])

    assert t["status"] == "READY"
    assert t["failed_step"] is None and t["error"] is None
    assert t["ready_at"] is not None


def test_retry_does_not_repeat_completed_steps(client):
    failed = create(client, fail_step="deploy")
    before = steps(failed)
    retry(client, failed["tenant_id"])
    after = steps(get(client, failed["tenant_id"]))

    # Completed steps were skipped: same attempt count and same timestamps.
    for name in ["validate", "provision_data", "configure"]:
        assert after[name]["status"] == "SUCCEEDED"
        assert after[name]["attempts"] == 1
        assert after[name]["finished_at"] == before[name]["finished_at"]
    # The failed step ran again; the step after it ran for the first time.
    assert after["deploy"]["attempts"] == 2 and after["deploy"]["status"] == "SUCCEEDED"
    assert after["verify"]["attempts"] == 1 and after["verify"]["status"] == "SUCCEEDED"


def test_retry_does_not_duplicate_data_provisioning(client):
    failed = create(client, fail_step="deploy")
    retry(client, failed["tenant_id"])
    t = get(client, failed["tenant_id"])
    cloud = client.app.state.cloud
    assert cloud.create_calls["database"] == 1
    assert steps(t)["provision_data"]["output"]["database_id"] == f"db-{t['tenant_id']}"


def test_adapter_idempotency_covers_lost_state_write(client):
    """Layer 2: the DB was created but the 'SUCCEEDED' write was lost (crash).
    The engine re-runs the step; the adapter reuses the existing database."""
    failed = create(client, fail_step="configure")
    repo = client.app.state.service.repo
    tenant = repo.get(failed["tenant_id"])
    tenant.step(StepName.PROVISION_DATA).status = StepStatus.PENDING  # simulate lost write
    repo.save(tenant)

    retry(client, failed["tenant_id"])
    t = get(client, failed["tenant_id"])
    assert t["status"] == "READY"
    assert steps(t)["provision_data"]["attempts"] == 2
    assert steps(t)["provision_data"]["output"]["created"] is False
    assert client.app.state.cloud.create_calls["database"] == 1


def test_retry_ready_tenant_is_conflict(client):
    t = create(client, "acme")
    assert t["status"] == "READY"
    r = retry(client, t["tenant_id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_tenant_state"
    assert get(client, t["tenant_id"])["status"] == "READY"  # unchanged


def test_retry_running_tenant_is_conflict(client):
    t = create(client, fail_step="deploy")
    repo = client.app.state.service.repo
    tenant = repo.get(t["tenant_id"])
    tenant.status = TenantStatus.DEPLOYING  # simulate a run in progress
    repo.save(tenant)
    assert retry(client, t["tenant_id"]).status_code == 409


def test_retry_unknown_tenant_is_404(client):
    assert retry(client, "does-not-exist").status_code == 404


def test_retry_of_bad_request_fails_again(client):
    """Documented contract: a bad request is fixed by a new request, not a retry."""
    t = create(client, "bad", region="mars-1")
    retry(client, t["tenant_id"])
    again = get(client, t["tenant_id"])
    assert again["status"] == "FAILED" and again["failed_step"] == "validate"
    assert steps(again)["validate"]["attempts"] == 2
