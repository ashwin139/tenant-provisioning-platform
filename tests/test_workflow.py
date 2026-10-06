"""Phase 3: multi-step workflow, failure capture, demo fault injection, metric."""
import pytest

from app.adapters import FakeCloud
from app.adapters.data import DataProvisioner
from app.models import Plan, Tenant, TenantModel

STEPS = ["validate", "provision_data", "configure", "deploy", "verify"]


def create(client, name="acme", **extra):
    body = {"name": name, "region": "ca-central-1", "plan": "standard", **extra}
    r = client.post("/api/v1/tenants", json=body)
    assert r.status_code == 202, r.text
    # TestClient runs background tasks before returning, so the workflow has finished.
    return client.get(f"/api/v1/tenants/{r.json()['tenant_id']}").json()


def statuses(tenant):
    return {s["name"]: s["status"] for s in tenant["steps"]}


def test_happy_path_reaches_ready(client):
    t = create(client)
    assert t["status"] == "READY"
    assert all(v == "SUCCEEDED" for v in statuses(t).values())
    assert t["ready_at"] and t["lead_time_seconds"] >= 0
    assert t["failed_step"] is None and t["error"] is None
    db = next(s for s in t["steps"] if s["name"] == "provision_data")
    assert db["output"]["database_id"] == f"db-{t['tenant_id']}"


def test_invalid_region_fails_at_validate(client):
    t = create(client, region="mars-1")
    assert t["status"] == "FAILED"
    assert t["failed_step"] == "validate"
    assert "mars-1" in t["error"]
    assert [statuses(t)[s] for s in STEPS] == ["FAILED", "PENDING", "PENDING", "PENDING", "PENDING"]


def test_injected_deploy_failure(client):
    t = create(client, "globex", fail_step="deploy")
    # 1-2. tenant ends FAILED, at the right step
    assert t["status"] == "FAILED"
    assert t["failed_step"] == "deploy"
    assert "Simulated deploy failure" in t["error"]
    # 3-4. earlier steps stay recorded as succeeded; later steps never ran
    assert [statuses(t)[s] for s in STEPS] == ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED", "FAILED", "PENDING"]
    assert t["ready_at"] is None
    # 5. no side effect from the failed or later steps
    cloud = client.app.state.cloud
    assert t["tenant_id"] not in cloud.deployments
    assert f"db-{t['tenant_id']}" in cloud.databases


@pytest.mark.parametrize("step", STEPS)
def test_fault_injection_works_for_every_step(client, step):
    t = create(client, f"t-{step.replace('_', '-')}", fail_step=step)
    assert t["status"] == "FAILED"
    assert t["failed_step"] == step
    idx = STEPS.index(step)
    assert all(statuses(t)[s] == "SUCCEEDED" for s in STEPS[:idx])
    assert all(statuses(t)[s] == "PENDING" for s in STEPS[idx + 1:])


def test_unknown_fail_step_is_rejected(client):
    r = client.post("/api/v1/tenants", json={"name": "acme", "region": "ca-central-1", "fail_step": "nope"})
    assert r.status_code == 422


def test_metrics_report_median_lead_time(client):
    create(client, "acme")
    create(client, "globex", fail_step="deploy")
    m = client.get("/api/v1/metrics").json()
    assert m["tenants_total"] == 2
    assert m["ready_total"] == 1 and m["failed_total"] == 1
    assert m["median_lead_time_seconds"] is not None


def test_data_provisioner_is_idempotent():
    cloud = FakeCloud()
    t = Tenant(name="acme", region="ca-central-1", plan=Plan.STANDARD, tenant_model=TenantModel.POOLED)
    first = DataProvisioner(cloud).run(t)
    second = DataProvisioner(cloud).run(t)
    assert first["database_id"] == second["database_id"]
    assert first["created"] is True and second["created"] is False
    assert cloud.create_calls["database"] == 1
