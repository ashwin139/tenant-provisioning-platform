"""FastAPI app: HTTP contract only. Business logic lives in TenantService."""
from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import DomainError
from .models import CreateTenantRequest, ErrorResponse, Tenant
from .repository import SqliteTenantRepository
from .service import TenantService
from .adapters import FakeCloud, build_adapters
from .workflow import WorkflowEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(db_path: str | None = None, step_delay_seconds: float | None = None) -> FastAPI:
    app = FastAPI(
        title="Tenant Provisioning API",
        version="0.1.0",
        description="Prototype self-service API for provisioning SaaS tenants.",
    )
    repo = SqliteTenantRepository(db_path or os.getenv("TENANT_DB_PATH", "tenants.db"))
    if step_delay_seconds is None:
        step_delay_seconds = float(os.getenv("SIM_STEP_DELAY_SECONDS", "0.6"))
    cloud = FakeCloud(delay_seconds=step_delay_seconds)
    engine = WorkflowEngine(repo, build_adapters(cloud))
    service = TenantService(repo, engine)
    app.state.service = service
    app.state.cloud = cloud  # exposed for tests

    # ---- errors: one structured shape for every failure -----------------------
    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request body is invalid",
                    "details": [
                        {"field": ".".join(str(p) for p in e["loc"][1:]), "msg": e["msg"]}
                        for e in exc.errors()
                    ],
                }
            },
        )

    errors = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}

    # ---- routes ---------------------------------------------------------------
    @app.post("/api/v1/tenants", status_code=202, response_model=Tenant, responses=errors)
    def create_tenant(req: CreateTenantRequest, background: BackgroundTasks) -> Tenant:
        """Accept a tenant request. Provisioning runs asynchronously; poll GET for status."""
        tenant = service.create(req)
        background.add_task(service.run_workflow, tenant.tenant_id)
        return tenant

    @app.get("/api/v1/tenants/{tenant_id}", response_model=Tenant, responses=errors)
    def get_tenant(tenant_id: str) -> Tenant:
        return service.get(tenant_id)

    @app.post("/api/v1/tenants/{tenant_id}/retry", status_code=202, response_model=Tenant, responses=errors)
    def retry_tenant(tenant_id: str, background: BackgroundTasks) -> Tenant:
        """Resume a FAILED tenant from its failed step. 409 if not FAILED."""
        tenant = service.retry(tenant_id)
        background.add_task(service.run_workflow, tenant.tenant_id)
        return tenant

    @app.get("/api/v1/metrics")
    def metrics() -> dict:
        """Primary metric: median lead time (request accepted -> READY)."""
        return service.metrics()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app
# Run with:  uvicorn app.main:create_app --factory --reload
