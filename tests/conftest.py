from __future__ import annotations

import pytest

from story_kernel.capabilities import CapabilityService
from story_kernel.contracts import ExecutionContext
from story_kernel.database import create_database


@pytest.fixture
def kernel_db():
    engine, sessions = create_database(":memory:")
    capabilities = CapabilityService(sessions)
    capabilities.ensure_world()
    yield engine, sessions, capabilities
    engine.dispose()


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext()

