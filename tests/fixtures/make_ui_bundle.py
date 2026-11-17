#!/usr/bin/env python3
"""Rebuild the fixture UI bundle in tests/fixtures/ui_bundle/ (Task 15).

    python3 tests/fixtures/make_ui_bundle.py

The bundle holds synthetic rows (tests/ui_sources.py) with the committed rules
and policy metrics. It lets the API and the UI run without pipeline data.
tests/test_ui_fixture_bundle.py fails when the committed copy no longer matches
what this script produces.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "src", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.service.export import write_bundle  # noqa: E402
from ui_sources import fixture_contents  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ui_bundle"


def main() -> int:
    checksum = write_bundle(fixture_contents(REPO_ROOT), FIXTURE_DIR, force=True)
    print(f"Wrote {FIXTURE_DIR} (SHA256SUMS {checksum})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
