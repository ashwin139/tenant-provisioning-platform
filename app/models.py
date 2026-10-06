"""Domain and API models.

One set of step names is used everywhere (API, CLI, engine). Each step maps to the
tenant state shown while that step runs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, computed_field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantModel(str, Enum):
    POOLED = "pooled"
    SILOED = "siloed"  # in the contract; not implemented by the prototype


class Plan(str, Enum):
    STARTER = "starter"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    PROVISIONING_DATA = "PROVISIONING_DATA"
    CONFIGURING = "CONFIGURING"
    DEPLOYING = "DEPLOYING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    FAILED = "FAILED"


class StepName(str, Enum):
    VALIDATE = "validate"
    PROVISION_DATA = "provision_data"
    CONFIGURE = "configure"
    DEPLOY = "deploy"
    VERIFY = "verify"


# Order matters: this is the workflow.
WORKFLOW: list[tuple[StepName, TenantStatus]] = [
    (StepName.VALIDATE, TenantStatus.VALIDATING),
    (StepName.PROVISION_DATA, TenantStatus.PROVISIONING_DATA),
    (StepName.CONFIGURE, TenantStatus.CONFIGURING),
    (StepName.DEPLOY, TenantStatus.DEPLOYING),
    (StepName.VERIFY, TenantStatus.VERIFYING),
]
STEP_STATE: dict[StepName, TenantStatus] = dict(WORKFLOW)


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class StepRecord(BaseModel):
    name: StepName
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    output: dict | None = None


# ---- API request -------------------------------------------------------------

class CreateTenantRequest(BaseModel):
    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$",
        description="DNS-safe tenant name, 3-32 chars, lowercase.",
        examples=["acme"],
    )
    region: str = Field(..., examples=["ca-central-1"])
    plan: Plan = Plan.STANDARD
    tenant_model: TenantModel = TenantModel.POOLED
    fail_step: StepName | None = Field(
        None,
        description="DEMO/TEST ONLY: fail this step on its first attempt. Not a production capability.",
    )


# ---- Tenant (stored and returned) ---------------------------------------------

class Tenant(BaseModel):
    tenant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    region: str
    plan: Plan
    tenant_model: TenantModel
    status: TenantStatus = TenantStatus.REQUESTED
    current_step: StepName | None = None
    failed_step: StepName | None = None
    error: str | None = None
    steps: list[StepRecord] = Field(
        default_factory=lambda: [StepRecord(name=s) for s, _ in WORKFLOW]
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ready_at: datetime | None = None
    fail_step: StepName | None = None  # demo-only fault injection

    def step(self, name: StepName) -> StepRecord:
        return next(s for s in self.steps if s.name == name)

    @computed_field  # the primary product metric, per tenant
    @property
    def lead_time_seconds(self) -> float | None:
        if self.ready_at is None:
            return None
        return (self.ready_at - self.created_at).total_seconds()


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
