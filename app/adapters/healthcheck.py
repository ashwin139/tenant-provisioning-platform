"""Step 5 — verify the tenant is actually usable (simulated).

Checks the simulated resources the earlier steps created, so READY means the
pieces exist, not just that the steps returned.
Production: an HTTP probe of the tenant endpoint plus a DB connectivity check.
"""
from __future__ import annotations

import logging

from app.models import Tenant

from .base import FakeCloud, StepFailed

log = logging.getLogger("tenant.adapters")


class HealthChecker:
    def __init__(self, cloud: FakeCloud):
        self.cloud = cloud

    def run(self, tenant: Tenant) -> dict:
        log.info("verify tenant=%s", tenant.name)
        self.cloud.simulate_latency()
        checks = {
            "database": f"db-{tenant.tenant_id}" in self.cloud.databases,
            "config": tenant.tenant_id in self.cloud.configs,
            "deployment": tenant.tenant_id in self.cloud.deployments,
        }
        missing = [name for name, ok in checks.items() if not ok]
        if missing:
            raise StepFailed(f"Health check failed; missing: {', '.join(missing)}")
        return {"healthy": True, "endpoint": self.cloud.deployments[tenant.tenant_id]["endpoint"]}
