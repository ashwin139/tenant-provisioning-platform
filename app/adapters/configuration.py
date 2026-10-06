"""Step 3 — write tenant configuration (simulated).

Idempotent: an upsert keyed by tenant id; repeating it produces the same config.
Production: a config service / feature-flag API adapter.
"""
from __future__ import annotations

import logging

from app.models import Plan, Tenant

from .base import FakeCloud

log = logging.getLogger("tenant.adapters")

PLAN_LIMITS = {
    Plan.STARTER: {"max_users": 10, "storage_gb": 5},
    Plan.STANDARD: {"max_users": 100, "storage_gb": 50},
    Plan.ENTERPRISE: {"max_users": 5000, "storage_gb": 1000},
}


class TenantConfigurator:
    def __init__(self, cloud: FakeCloud):
        self.cloud = cloud

    def run(self, tenant: Tenant) -> dict:
        log.info("configure tenant=%s plan=%s", tenant.name, tenant.plan.value)
        self.cloud.simulate_latency()
        config = {"plan": tenant.plan.value, **PLAN_LIMITS[tenant.plan]}
        self.cloud.configs[tenant.tenant_id] = config  # upsert
        return config
