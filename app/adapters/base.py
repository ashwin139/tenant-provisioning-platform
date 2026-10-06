"""Adapter contract shared by every provisioning step.

Adapters own side effects. The workflow engine owns order and state.
Every adapter MUST be safe to call more than once for the same tenant.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Protocol

from app.models import Tenant


class StepFailed(Exception):
    """An expected, reportable step failure (bad input, dependency down, ...)."""


class StepAdapter(Protocol):
    def run(self, tenant: Tenant) -> dict:
        """Do the step's work for this tenant and return a small result dict."""
        ...


class FakeCloud:
    """Stand-in for the external systems (database service, config store,
    deployment platform).

    Like real infrastructure it outlives the API process: when `state_path` is
    set, its state is saved to a JSON file, so a restart doesn't "forget"
    resources that earlier steps created.

    `create_calls` counts real resource creations so tests can prove that
    repeated calls do not duplicate work.
    """

    KINDS = ("databases", "configs", "deployments")

    def __init__(self, delay_seconds: float = 0.0, state_path: str | None = None):
        self.delay_seconds = delay_seconds
        self.state_path = state_path
        self._lock = threading.Lock()
        self.databases: dict[str, dict] = {}
        self.configs: dict[str, dict] = {}
        self.deployments: dict[str, dict] = {}
        self.create_calls: dict[str, int] = {"database": 0}
        if state_path and os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                saved = json.load(f)
            for kind in self.KINDS:
                getattr(self, kind).update(saved.get(kind, {}))
            self.create_calls.update(saved.get("create_calls", {}))

    def put(self, kind: str, key: str, value: dict) -> None:
        """Create or replace a resource (an upsert)."""
        with self._lock:
            getattr(self, kind)[key] = value
            if kind == "databases":
                self.create_calls["database"] += 1
            self._save()

    def _save(self) -> None:
        if not self.state_path:
            return
        state = {kind: getattr(self, kind) for kind in self.KINDS}
        state["create_calls"] = self.create_calls
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def simulate_latency(self) -> None:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
