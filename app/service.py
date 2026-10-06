"""Tenant service: the business operations behind the API routes.

Route handlers call this; they hold no business logic themselves.
"""
from __future__ import annotations

from .errors import TenantNotFound, UnsupportedTenantModel
from .models import CreateTenantRequest, Tenant, TenantModel
from .repository import TenantRepository


class TenantService:
    def __init__(self, repo: TenantRepository):
        self.repo = repo

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
        )
        self.repo.add(tenant)  # raises DuplicateTenantName
        return tenant

    def get(self, tenant_id: str) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if tenant is None:
            raise TenantNotFound(f"Tenant '{tenant_id}' not found")
        return tenant
