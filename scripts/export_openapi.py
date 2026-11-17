#!/usr/bin/env python3
"""Write the OpenAPI contract of the recommendation API (Task 15).

    python3 scripts/export_openapi.py

The contract is generated from the app running on the fixture bundle, so it
needs no pipeline data. tests/test_api.py fails when the committed file no
longer matches the app.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.service.api import create_app  # noqa: E402

FIXTURE_BUNDLE = REPO_ROOT / "tests" / "fixtures" / "ui_bundle"
OPENAPI_PATH = REPO_ROOT / "docs" / "design" / "recommendation_api_openapi.json"


def openapi_text() -> str:
    return json.dumps(create_app(FIXTURE_BUNDLE).openapi(), indent=2) + "\n"


def main() -> int:
    OPENAPI_PATH.write_text(openapi_text(), encoding="utf-8")
    print(f"Wrote {OPENAPI_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
