"""Adapter contract shared by every provisioning step.

Adapters own side effects. The workflow engine owns order and state.
Every adapter MUST be safe to call more than once for the same tenant.
"""
from __future__ import annotations

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
    deployment platform). In-memory on purpose: it plays the role of
    infrastructure that lives outside the platform's own state.

    `create_calls` counts real resource creations so tests can prove that
    repeated calls do not duplicate work.
    """

    def __init__(self, delay_seconds: float = 0.0):
        self.delay_seconds = delay_seconds
        self.databases: dict[str, dict] = {}
        self.configs: dict[str, dict] = {}
        self.deployments: dict[str, dict] = {}
        self.create_calls: dict[str, int] = {"database": 0}

    def simulate_latency(self) -> None:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
