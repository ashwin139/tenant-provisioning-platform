"""Phase 7 review fixes: interrupted runs are recoverable; unexpected errors keep the error shape."""
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import StepName, StepStatus, TenantStatus


def test_run_interrupted_by_restart_becomes_retryable(tmp_path):
    db = str(tmp_path / "t.db")
    app1 = create_app(db_path=db, step_delay_seconds=0)
    with TestClient(app1) as c:
        tid = c.post("/api/v1/tenants", json={"name": "acme", "region": "ca-central-1"}).json()["tenant_id"]

    # Simulate the process dying mid-deploy: state says DEPLOYING / RUNNING.
    repo = app1.state.service.repo
    t = repo.get(tid)
    t.status, t.current_step, t.ready_at = TenantStatus.DEPLOYING, StepName.DEPLOY, None
    t.step(StepName.DEPLOY).status = StepStatus.RUNNING
    t.step(StepName.VERIFY).status = StepStatus.PENDING
    repo.save(t)

    # "Restart": a new app on the same database reconciles the orphaned run.
    app2 = create_app(db_path=db, step_delay_seconds=0)
    with TestClient(app2) as c:
        after = c.get(f"/api/v1/tenants/{tid}").json()
        assert after["status"] == "FAILED"
        assert after["failed_step"] == "deploy"
        assert "Interrupted" in after["error"]

        assert c.post(f"/api/v1/tenants/{tid}/retry").status_code == 202
        assert c.get(f"/api/v1/tenants/{tid}").json()["status"] == "READY"


def test_unexpected_error_uses_error_shape(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path / "t.db"), step_delay_seconds=0)

    def boom(_):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(app.state.service, "get", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/tenants/x")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Unexpected server error"}}
