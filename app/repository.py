"""Tenant persistence.

Prototype choice: SQLite (stdlib), one row per tenant, the tenant stored as a JSON
document. State survives an API restart, which the retry story depends on.
Production: Postgres, plus workflow history in the orchestrator.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from typing import Protocol

from .errors import DuplicateTenantName
from .models import Tenant, TenantStatus, utcnow


class TenantRepository(Protocol):
    def add(self, tenant: Tenant) -> None: ...
    def get(self, tenant_id: str) -> Tenant | None: ...
    def save(self, tenant: Tenant) -> None: ...
    def list(self) -> list[Tenant]: ...
    def update_if_status(
        self, tenant_id: str, expected: TenantStatus, mutate: Callable[[Tenant], None]
    ) -> Tenant | None: ...


class SqliteTenantRepository:
    def __init__(self, path: str = "tenants.db"):
        # The workflow runs in a background thread, so the connection is shared
        # across threads and guarded by a lock.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS tenants (
                       tenant_id TEXT PRIMARY KEY,
                       name      TEXT NOT NULL UNIQUE,
                       data      TEXT NOT NULL
                   )"""
            )

    def add(self, tenant: Tenant) -> None:
        try:
            with self._lock, self._conn:
                self._conn.execute(
                    "INSERT INTO tenants (tenant_id, name, data) VALUES (?, ?, ?)",
                    (tenant.tenant_id, tenant.name, tenant.model_dump_json()),
                )
        except sqlite3.IntegrityError:
            raise DuplicateTenantName(f"A tenant named '{tenant.name}' already exists")

    def get(self, tenant_id: str) -> Tenant | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
        return Tenant.model_validate_json(row[0]) if row else None

    def save(self, tenant: Tenant) -> None:
        tenant.updated_at = utcnow()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE tenants SET data = ? WHERE tenant_id = ?",
                (tenant.model_dump_json(), tenant.tenant_id),
            )

    def list(self) -> list[Tenant]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM tenants").fetchall()
        return [Tenant.model_validate_json(r[0]) for r in rows]

    def update_if_status(
        self, tenant_id: str, expected: TenantStatus, mutate: Callable[[Tenant], None]
    ) -> Tenant | None:
        """Read-check-write under one lock: apply `mutate` only if the tenant is
        currently in `expected` status. Returns the updated tenant, or None if the
        status did not match. Stops two concurrent retries both starting a run.
        (Production: a conditional UPDATE / row version in Postgres.)"""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT data FROM tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
            if row is None:
                return None
            tenant = Tenant.model_validate_json(row[0])
            if tenant.status is not expected:
                return None
            mutate(tenant)
            tenant.updated_at = utcnow()
            self._conn.execute(
                "UPDATE tenants SET data = ? WHERE tenant_id = ?",
                (tenant.model_dump_json(), tenant.tenant_id),
            )
            return tenant
