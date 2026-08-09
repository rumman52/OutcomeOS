import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="session")
def tenant_ids() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (Path(__file__).parent / "fixtures" / "tenants.json").read_text()
    )
    return value
