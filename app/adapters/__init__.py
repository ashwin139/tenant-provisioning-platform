"""Simulated provisioning adapters (one per workflow step)."""
from app.models import StepName

from .base import FakeCloud, StepAdapter, StepFailed
from .configuration import TenantConfigurator
from .data import DataProvisioner
from .deployment import Deployer
from .healthcheck import HealthChecker
from .validation import RequestValidator


def build_adapters(cloud: FakeCloud) -> dict[StepName, StepAdapter]:
    return {
        StepName.VALIDATE: RequestValidator(cloud),
        StepName.PROVISION_DATA: DataProvisioner(cloud),
        StepName.CONFIGURE: TenantConfigurator(cloud),
        StepName.DEPLOY: Deployer(cloud),
        StepName.VERIFY: HealthChecker(cloud),
    }


__all__ = ["FakeCloud", "StepAdapter", "StepFailed", "build_adapters"]
