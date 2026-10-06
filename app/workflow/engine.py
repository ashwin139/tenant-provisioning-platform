"""Hand-written workflow engine: a linear state machine over WORKFLOW.

Rules:
- Every transition is persisted before the next step starts.
- Any exception in a step marks the step and tenant FAILED (never left RUNNING).
- A tenant becomes READY only after all steps have SUCCEEDED.
- Steps already SUCCEEDED are skipped, so the same run() both starts and resumes.

Production replacement point: this class is what Temporal / Step Functions
replaces; the adapters and API contract stay the same.
"""
from __future__ import annotations

import logging

from app.models import WORKFLOW, StepName, StepRecord, StepStatus, Tenant, TenantStatus, utcnow
from app.repository import TenantRepository
from app.adapters.base import StepAdapter, StepFailed

log = logging.getLogger("tenant.workflow")


class WorkflowEngine:
    def __init__(self, repo: TenantRepository, adapters: dict[StepName, StepAdapter]):
        self.repo = repo
        self.adapters = adapters

    def run(self, tenant_id: str) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if tenant is None:
            raise ValueError(f"unknown tenant {tenant_id}")
        log.info("workflow start tenant=%s", tenant.name)

        for step_name, running_state in WORKFLOW:
            record = tenant.step(step_name)
            if record.status is StepStatus.SUCCEEDED:
                # Resume: completed work is never re-executed (idempotency layer 1).
                log.info("step %s already SUCCEEDED, skipping tenant=%s", step_name.value, tenant.name)
                continue
            self._mark_running(tenant, record, running_state)
            try:
                self._inject_fault_if_requested(tenant, record)
                output = self.adapters[step_name].run(tenant)
            except Exception as exc:  # noqa: BLE001 - any failure must be recorded
                self._mark_failed(tenant, record, exc)
                return tenant
            self._mark_succeeded(tenant, record, output)

        tenant.status = TenantStatus.READY
        tenant.current_step = None
        tenant.ready_at = utcnow()
        self.repo.save(tenant)
        log.info("workflow READY tenant=%s lead_time=%.2fs", tenant.name, tenant.lead_time_seconds)
        return tenant

    def recover_interrupted(self, tenant: Tenant) -> bool:
        """Called at startup. A tenant that is neither READY nor FAILED was
        mid-run when the process stopped; nothing will ever finish it. Mark it
        FAILED at the step it was on so the normal retry path can resume it.
        Re-running that step is safe because adapters are idempotent."""
        if tenant.status in (TenantStatus.READY, TenantStatus.FAILED):
            return False
        record = next(s for s in tenant.steps if s.status is not StepStatus.SUCCEEDED)
        self._mark_failed(
            tenant, record, StepFailed("Interrupted: the API stopped before this step finished")
        )
        return True

    # ---- transitions ----------------------------------------------------------

    def _mark_running(self, tenant: Tenant, record: StepRecord, state: TenantStatus) -> None:
        tenant.status = state
        tenant.current_step = record.name
        record.status = StepStatus.RUNNING
        record.attempts += 1
        record.started_at = utcnow()
        record.finished_at = None
        record.error = None
        self.repo.save(tenant)

    def _mark_succeeded(self, tenant: Tenant, record: StepRecord, output: dict) -> None:
        record.status = StepStatus.SUCCEEDED
        record.output = output
        record.finished_at = utcnow()
        self.repo.save(tenant)
        log.info("step %s SUCCEEDED tenant=%s", record.name.value, tenant.name)

    def _mark_failed(self, tenant: Tenant, record: StepRecord, exc: Exception) -> None:
        message = str(exc) if isinstance(exc, StepFailed) else f"{type(exc).__name__}: {exc}"
        record.status = StepStatus.FAILED
        record.error = message
        record.finished_at = utcnow()
        tenant.status = TenantStatus.FAILED
        tenant.failed_step = record.name
        tenant.error = message
        self.repo.save(tenant)
        log.warning("step %s FAILED tenant=%s error=%s", record.name.value, tenant.name, message)

    # ---- demo-only fault injection ---------------------------------------------

    @staticmethod
    def _inject_fault_if_requested(tenant: Tenant, record: StepRecord) -> None:
        """DEMO/TEST ONLY. Fails the named step on its FIRST attempt, so a plain
        retry succeeds. Kept in the engine so adapters stay free of test hooks.
        Not a production capability; removed in the production build."""
        if tenant.fail_step == record.name and record.attempts == 1:
            raise StepFailed(f"Simulated {record.name.value} failure (demo fault injection)")
