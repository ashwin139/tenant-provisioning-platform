"""Step 2 — provision the tenant's data store (simulated).

Idempotent: the resource id is derived from the tenant id, and an existing
resource is reused instead of creating a second one.
Production: a Terraform/RDS or schema-per-tenant adapter with the same contract.
"""
from __future__ import annotations

import logging

from app.models import Tenant

from .base import FakeCloud

log = logging.getLogger("tenant.adapters")


class DataProvisioner:
    def __init__(self, cloud: FakeCloud):
        self.cloud = cloud

    def run(self, tenant: Tenant) -> dict:
        db_id = f"db-{tenant.tenant_id}"
        if db_id in self.cloud.databases:
            log.info("provision_data tenant=%s reusing %s", tenant.name, db_id)
            return {"database_id": db_id, "created": False}

        log.info("provision_data tenant=%s creating %s", tenant.name, db_id)
        self.cloud.simulate_latency()
        self.cloud.put("databases", db_id, {"tenant_id": tenant.tenant_id, "region": tenant.region})
        return {"database_id": db_id, "created": True}
