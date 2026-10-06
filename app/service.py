"""Tenant service: the business operations behind the API routes.

Route handlers call this; they hold no business logic themselves.
"""
from __future__ import annotations

from statistics import median

from .errors import InvalidTenantState, TenantNotFound, UnsupportedTenantModel
from .models import CreateTenantRequest, Tenant, TenantModel, TenantStatus
from .repository import TenantRepository
from .workflow import WorkflowEngine


class TenantService:
    def __init__(self, repo: TenantRepository, engine: WorkflowEngine):
        self.repo = repo
        self.engine = engine

    def create(self, req: CreateTenantRequest) -> Tenant:
        if req.tenant_model is TenantModel.SILOED:
            raise UnsupportedTenantModel(
                "tenant_model 'siloed' is part of the API contract but not supported "
                "by this prototype; use 'pooled'"
            )
        tenant = Tenant(
            name=req.name,
            region=req.region,
            plan=req.plan,
            tenant_model=req.tenant_model,
            fail_step=req.fail_step,
        )
        self.repo.add(tenant)  # raises DuplicateTenantName
        return tenant

    def get(self, tenant_id: str) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if tenant is None:
            raise TenantNotFound(f"Tenant '{tenant_id}' not found")
        return tenant

    def retry(self, tenant_id: str) -> Tenant:
        """Re-queue a FAILED tenant. The engine then resumes at the failed step.

        Contract: only FAILED tenants can be retried. A running or READY tenant
        returns 409, so retry is never a hidden "re-provision".
        """
        current = self.get(tenant_id)  # 404 if unknown

        def requeue(t: Tenant) -> None:
            t.status = TenantStatus.REQUESTED
            t.current_step = None
            t.failed_step = None
            t.error = None

        tenant = self.repo.update_if_status(tenant_id, TenantStatus.FAILED, requeue)
        if tenant is None:
            raise InvalidTenantState(
                f"Tenant is {current.status.value}; only FAILED tenants can be retried"
            )
        return tenant

    def run_workflow(self, tenant_id: str) -> Tenant:
        """Executed in the background after the API has answered 202 (create or retry)."""
        return self.engine.run(tenant_id)

    def metrics(self) -> dict:
        tenants = self.repo.list()
        lead_times = [t.lead_time_seconds for t in tenants if t.lead_time_seconds is not None]
        by_status: dict[str, int] = {}
        for t in tenants:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {
            "tenants_total": len(tenants),
            "tenants_by_status": by_status,
            "ready_total": by_status.get(TenantStatus.READY.value, 0),
            "failed_total": by_status.get(TenantStatus.FAILED.value, 0),
            "median_lead_time_seconds": round(median(lead_times), 3) if lead_times else None,
        }
