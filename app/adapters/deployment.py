"""Step 4 — deploy / route the tenant on the application (simulated).

Pooled tenancy: no new stack, just register the tenant's route on the shared app.
Idempotent: upsert keyed by tenant id.
Production: a Kubernetes/GitOps or ingress/router adapter.
"""
from __future__ import annotations

import logging

from app.models import Tenant

from .base import FakeCloud

log = logging.getLogger("tenant.adapters")


class Deployer:
    def __init__(self, cloud: FakeCloud):
        self.cloud = cloud

    def run(self, tenant: Tenant) -> dict:
        endpoint = f"https://{tenant.name}.app.example.com"
        log.info("deploy tenant=%s endpoint=%s", tenant.name, endpoint)
        self.cloud.simulate_latency()
        self.cloud.deployments[tenant.tenant_id] = {"endpoint": endpoint, "pool": f"pool-{tenant.region}"}
        return {"endpoint": endpoint}
