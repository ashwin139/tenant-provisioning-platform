"""Step 1 — validate the request against platform rules.

Shape validation (name format, enum values) happens at the API. This step checks
platform policy, which can change without changing the API contract.
"""
from __future__ import annotations

import logging

from app.models import Tenant

from .base import FakeCloud, StepFailed

log = logging.getLogger("tenant.adapters")

ALLOWED_REGIONS = {"ca-central-1", "us-east-1", "eu-west-1"}


class RequestValidator:
    def __init__(self, cloud: FakeCloud):
        self.cloud = cloud

    def run(self, tenant: Tenant) -> dict:
        log.info("validate tenant=%s region=%s plan=%s", tenant.name, tenant.region, tenant.plan.value)
        self.cloud.simulate_latency()
        if tenant.region not in ALLOWED_REGIONS:
            raise StepFailed(
                f"Region '{tenant.region}' is not offered. Allowed: {', '.join(sorted(ALLOWED_REGIONS))}"
            )
        return {"region": tenant.region, "plan": tenant.plan.value}
