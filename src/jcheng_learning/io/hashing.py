"""SHA-256 helpers and the ``SHA256SUMS`` format.

Rules (see ``docs/m1/04-DATA-CONTRACT.md`` §2.2):

- ``SHA256SUMS`` covers every regular file except itself.
- Lines are ``<64 lowercase hex>  <relative/path>``, sorted by path bytes.
- The dataset never stores a hash of ``SHA256SUMS``; the quality report does.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..errors import DatasetError

SUMS_NAME = "SHA256SUMS"
_CHUNK = 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(_CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _payload_files(root: Path) -> list[Path]:
    root = Path(root)
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.name == SUMS_NAME:
            continue
        if path.is_symlink():
            raise DatasetError(f"symlink is not allowed in a dataset: {path}")
        if path.is_file():
            files.append(path)
    return files


def write_sha256sums(root: Path) -> Path:
    """Write ``SHA256SUMS`` for every file under *root* (except itself)."""

    root = Path(root)
    files = _payload_files(root)
    lines = []
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        lines.append(f"{file_sha256(path)}  {rel}")
    target = root / SUMS_NAME
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target


def read_sha256sums(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"missing {path.name}: {path}")
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise DatasetError(f"{path.name}:{number}: empty line")
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise DatasetError(f"{path.name}:{number}: expected '<hash>  <path>'")
        digest, rel = parts
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise DatasetError(f"{path.name}:{number}: invalid sha256")
        if rel in result:
            raise DatasetError(f"{path.name}:{number}: duplicate path {rel}")
        result[rel] = digest
    return result


def verify_sha256sums(root: Path, *, require_complete: bool = True) -> list[str]:
    """Return a list of problems; an empty list means the tree matches."""

    root = Path(root)
    problems: list[str] = []
    sums = read_sha256sums(root / SUMS_NAME)
    for rel, expected in sums.items():
        path = root / rel
        if not path.is_file():
            problems.append(f"missing file: {rel}")
            continue
        actual = file_sha256(path)
        if actual != expected:
            problems.append(f"hash mismatch: {rel}")
    if require_complete:
        covered = set(sums)
        for path in _payload_files(root):
            rel = path.relative_to(root).as_posix()
            if rel not in covered:
                problems.append(f"file not covered by {SUMS_NAME}: {rel}")
    return problems


def root_hash(root: Path) -> str:
    """SHA-256 of the ``SHA256SUMS`` file (the dataset content root)."""

    return file_sha256(Path(root) / SUMS_NAME)
