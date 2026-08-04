import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def tenant_ids():
    return json.loads((Path(__file__).parent / "fixtures" / "tenants.json").read_text())
