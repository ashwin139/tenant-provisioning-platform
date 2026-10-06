"""Phase 6: the CLI drives the real API (in-process) over HTTP."""
import re

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import cli
from app.main import create_app

runner = CliRunner()


@pytest.fixture
def api(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path / "cli.db"), step_delay_seconds=0)
    monkeypatch.setattr(cli, "make_client", lambda: TestClient(app))
    return app


def tenant_id(output: str) -> str:
    return re.search(r"Tenant ID:\s+(\S+)", output).group(1)


def test_happy_path(api):
    r = runner.invoke(cli.app, ["create-tenant", "acme"])
    assert r.exit_code == 0, r.output
    for label in ["Validate", "Provision data", "Configure tenant", "Deploy application", "Verify health"]:
        assert f"✓ {label}" in r.output
    assert "Status:    READY" in r.output


def test_failure_then_retry(api):
    r = runner.invoke(cli.app, ["create-tenant", "globex", "--fail-step", "deploy"])
    assert r.exit_code == 1, r.output
    assert "✓ Configure tenant" in r.output
    assert "✗ Deploy application" in r.output
    assert "Verify health" not in r.output
    assert "Status:    FAILED" in r.output and "Failed step: deploy" in r.output

    r2 = runner.invoke(cli.app, ["retry", tenant_id(r.output)])
    assert r2.exit_code == 0, r2.output
    assert "- Validate: already complete" in r2.output
    assert "- Configure tenant: already complete" in r2.output
    assert "✓ Deploy application" in r2.output and "✓ Verify health" in r2.output
    assert "✓ Validate" not in r2.output  # not re-run
    assert "Status:    READY" in r2.output


def test_status_shows_steps(api):
    r = runner.invoke(cli.app, ["create-tenant", "acme"])
    s = runner.invoke(cli.app, ["status", tenant_id(r.output)])
    assert s.exit_code == 0
    assert "SUCCEEDED" in s.output and "READY" in s.output


def test_api_errors_are_readable(api):
    runner.invoke(cli.app, ["create-tenant", "acme"])
    dup = runner.invoke(cli.app, ["create-tenant", "acme"])
    assert dup.exit_code == 1 and "duplicate_tenant_name" in dup.output
    silo = runner.invoke(cli.app, ["create-tenant", "initech", "--tenant-model", "siloed"])
    assert silo.exit_code == 1 and "unsupported_tenant_model" in silo.output
    missing = runner.invoke(cli.app, ["status", "nope"])
    assert missing.exit_code == 1 and "tenant_not_found" in missing.output


def test_validation_failure_advises_new_request(api):
    r = runner.invoke(cli.app, ["create-tenant", "bad", "--region", "mars-1"])
    assert r.exit_code == 1
    assert "✗ Validate" in r.output
    assert "new request" in r.output and "cli.py retry" not in r.output


def test_api_down_is_reported(monkeypatch):
    import httpx

    def refused():
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(cli, "make_client", refused)
    r = runner.invoke(cli.app, ["status", "x"])
    assert r.exit_code == 2 and "Cannot reach the API" in r.output
