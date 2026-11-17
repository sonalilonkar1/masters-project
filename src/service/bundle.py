"""Read and check the UI bundle (Task 15 Part C).

``SHA256SUMS`` lists every bundle file except itself, in the format written by
``sha256sum``. A bundle is usable only when every listed file exists with its
recorded checksum and no unlisted file is present.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CHECKSUM_FILE = "SHA256SUMS"


class BundleIntegrityError(RuntimeError):
    """A bundle file is missing, changed or not listed in SHA256SUMS."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 24), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_files(bundle_dir: Path) -> list[str]:
    """Every file in the bundle except SHA256SUMS, as sorted POSIX paths relative to the bundle."""
    bundle_dir = Path(bundle_dir)
    return sorted(
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.relative_to(bundle_dir).as_posix() != CHECKSUM_FILE
    )


def write_checksums(bundle_dir: Path) -> str:
    """Write SHA256SUMS for every bundle file; return the checksum of SHA256SUMS itself."""
    bundle_dir = Path(bundle_dir)
    lines = "".join(f"{_sha256(bundle_dir / name)}  {name}\n" for name in bundle_files(bundle_dir))
    (bundle_dir / CHECKSUM_FILE).write_text(lines, encoding="utf-8")
    return _sha256(bundle_dir / CHECKSUM_FILE)


def read_checksums(bundle_dir: Path) -> dict[str, str]:
    path = Path(bundle_dir) / CHECKSUM_FILE
    if not path.is_file():
        raise BundleIntegrityError(f"{path} is missing")
    recorded = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name or name in recorded:
            raise BundleIntegrityError(f"{path}:{number}: malformed or duplicate line")
        recorded[name] = digest
    return recorded


def verify_bundle(bundle_dir: Path) -> str:
    """Check every file against SHA256SUMS; return the checksum of SHA256SUMS (the bundle checksum)."""
    bundle_dir = Path(bundle_dir)
    recorded = read_checksums(bundle_dir)
    present = set(bundle_files(bundle_dir))

    problems = [f"missing: {name}" for name in sorted(set(recorded) - present)]
    problems += [f"not listed in {CHECKSUM_FILE}: {name}" for name in sorted(present - set(recorded))]
    problems += [
        f"changed: {name}"
        for name in sorted(set(recorded) & present)
        if _sha256(bundle_dir / name) != recorded[name]
    ]
    if problems:
        raise BundleIntegrityError(f"{bundle_dir}: " + "; ".join(problems))
    return _sha256(bundle_dir / CHECKSUM_FILE)
