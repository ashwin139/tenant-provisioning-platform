"""Developer CLI for the Tenant Provisioning API.

A thin HTTP client: every command goes through the REST API, never around it.

    python cli.py create-tenant acme --region ca-central-1 --plan standard
    python cli.py create-tenant globex --fail-step deploy      # demo-only failure
    python cli.py status <tenant-id>
    python cli.py retry <tenant-id>
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False, help="Self-service tenant provisioning (prototype).")
console = Console()

API_URL = os.getenv("TENANT_API_URL", "http://127.0.0.1:8000")
POLL_INTERVAL = float(os.getenv("TENANT_CLI_POLL_SECONDS", "0.3"))
TIMEOUT_SECONDS = 120

STEP_LABELS = {
    "validate": "Validate",
    "provision_data": "Provision data",
    "configure": "Configure tenant",
    "deploy": "Deploy application",
    "verify": "Verify health",
}
TERMINAL = {"READY", "FAILED"}


# ---- HTTP plumbing -------------------------------------------------------------

def make_client() -> httpx.Client:
    """Overridden in tests to point at an in-process app."""
    return httpx.Client(base_url=API_URL, timeout=10)


def call(method: str, path: str, **kwargs) -> dict:
    """Call the API; turn transport and API errors into clean CLI messages."""
    try:
        with make_client() as client:
            r = client.request(method, path, **kwargs)
    except httpx.ConnectError:
        console.print(f"[red]✗ Cannot reach the API at {API_URL}[/red]")
        console.print("  Start it with: uvicorn app.main:create_app --factory")
        raise typer.Exit(2)
    if r.status_code >= 400:
        try:
            err = r.json()["error"]
            console.print(f"[red]✗ {err['message']}[/red]  [dim]({r.status_code} {err['code']})[/dim]")
            for d in err.get("details") or []:
                console.print(f"  - {d['field']}: {d['msg']}")
        except (ValueError, KeyError):
            console.print(f"[red]✗ API error {r.status_code}: {r.text}[/red]")
        raise typer.Exit(1)
    return r.json()


# ---- rendering -----------------------------------------------------------------

def step_detail(step: dict) -> str:
    out = step.get("output") or {}
    if out.get("healthy"):
        return "  [dim]healthy[/dim]"
    for key in ("database_id", "endpoint"):
        if key in out:
            return f"  [dim]{out[key]}[/dim]"
    return ""


def follow(tenant: dict) -> dict:
    """Poll the tenant and print each step as it finishes in THIS run.

    Steps already SUCCEEDED when we start (a retry) are reported as already
    complete; a step counts as finished only if its attempts went up since then.
    """
    tenant_id = tenant["tenant_id"]
    baseline = {s["name"]: s["attempts"] for s in tenant["steps"]}
    reported: set[str] = set()

    for s in tenant["steps"]:
        if s["status"] == "SUCCEEDED":
            console.print(f"  [dim]- {STEP_LABELS[s['name']]}: already complete[/dim]")
            reported.add(s["name"])

    deadline = time.monotonic() + TIMEOUT_SECONDS
    with console.status("Provisioning...") as spinner:
        while True:
            tenant = call("GET", f"/api/v1/tenants/{tenant_id}")
            for s in tenant["steps"]:
                name = s["name"]
                ran_now = s["attempts"] > baseline[name]
                if name in reported or not ran_now:
                    continue
                if s["status"] == "SUCCEEDED":
                    console.print(f"[green]✓[/green] {STEP_LABELS[name]}{step_detail(s)}")
                    reported.add(name)
                elif s["status"] == "FAILED":
                    console.print(f"[red]✗ {STEP_LABELS[name]}[/red]")
                    reported.add(name)
                elif s["status"] == "RUNNING":
                    spinner.update(f"{STEP_LABELS[name]}...")
            if tenant["status"] in TERMINAL:
                return tenant
            if time.monotonic() > deadline:
                console.print(f"[yellow]Still running after {TIMEOUT_SECONDS}s; check later with:[/yellow]")
                console.print(f"  python cli.py status {tenant_id}")
                raise typer.Exit(3)
            time.sleep(POLL_INTERVAL)


def summary(tenant: dict) -> None:
    console.print()
    console.print(f"Tenant ID: [bold]{tenant['tenant_id']}[/bold]")
    colour = {"READY": "green", "FAILED": "red"}.get(tenant["status"], "yellow")
    console.print(f"Status:    [bold {colour}]{tenant['status']}[/bold {colour}]")
    if tenant["status"] == "READY":
        verify = next(s for s in tenant["steps"] if s["name"] == "verify")
        console.print(f"Endpoint:  {(verify.get('output') or {}).get('endpoint', '-')}")
        console.print(f"Lead time: {tenant['lead_time_seconds']:.1f}s")
    if tenant["status"] == "FAILED":
        console.print(f"Failed step: {tenant['failed_step']}")
        console.print(f"Error:       {tenant['error']}")
        if tenant["failed_step"] == "validate":
            console.print("[dim]Next: retrying will fail the same way; submit a new request "
                          "with corrected input (the name stays reserved by this request).[/dim]")
        else:
            console.print(f"[dim]Next: python cli.py retry {tenant['tenant_id']}[/dim]")


def finish(tenant: dict) -> None:
    summary(tenant)
    raise typer.Exit(0 if tenant["status"] == "READY" else 1)


# ---- commands ------------------------------------------------------------------

@app.command("create-tenant")
def create_tenant(
    name: str = typer.Argument(..., help="DNS-safe tenant name, e.g. acme"),
    region: str = typer.Option("ca-central-1", help="ca-central-1 | us-east-1 | eu-west-1"),
    plan: str = typer.Option("standard", help="starter | standard | enterprise"),
    tenant_model: str = typer.Option("pooled", help="pooled (siloed is not supported yet)"),
    fail_step: Optional[str] = typer.Option(
        None, help="DEMO ONLY: fail this step on its first attempt "
                   "(validate|provision_data|configure|deploy|verify)"),
    wait: bool = typer.Option(True, help="Follow progress until READY or FAILED."),
):
    """Request a new tenant and follow it to READY or FAILED."""
    body = {"name": name, "region": region, "plan": plan, "tenant_model": tenant_model}
    if fail_step:
        body["fail_step"] = fail_step
        console.print(f"[yellow]Demo: injecting a failure at '{fail_step}'[/yellow]")
    console.print(f"Creating tenant: [bold]{name}[/bold]\n")
    tenant = call("POST", "/api/v1/tenants", json=body)
    if not wait:
        console.print(f"Accepted. Tenant ID: {tenant['tenant_id']}")
        return
    finish(follow(tenant))


@app.command()
def retry(tenant_id: str = typer.Argument(..., help="ID of a FAILED tenant")):
    """Resume a FAILED tenant from its failed step."""
    console.print("Resuming tenant...\n")
    tenant = call("POST", f"/api/v1/tenants/{tenant_id}/retry")
    finish(follow(tenant))


@app.command()
def status(
    tenant_id: str = typer.Argument(...),
    watch: bool = typer.Option(False, help="Follow until READY or FAILED."),
):
    """Show a tenant and its workflow steps."""
    tenant = call("GET", f"/api/v1/tenants/{tenant_id}")
    if watch and tenant["status"] not in TERMINAL:
        tenant = follow(tenant)

    table = Table(title=f"{tenant['name']} ({tenant['region']}, {tenant['plan']})")
    for col in ("Step", "Status", "Attempts", "Detail"):
        table.add_column(col)
    colours = {"SUCCEEDED": "green", "FAILED": "red", "RUNNING": "yellow", "PENDING": "dim"}
    for s in tenant["steps"]:
        c = colours[s["status"]]
        detail = s.get("error") or step_detail(s).strip()
        table.add_row(STEP_LABELS[s["name"]], f"[{c}]{s['status']}[/{c}]", str(s["attempts"]), detail)
    console.print(table)
    summary(tenant)


if __name__ == "__main__":
    app()
