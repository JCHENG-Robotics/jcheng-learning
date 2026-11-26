"""Provenance helpers shared by generators and importers."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .version import CONTRACT_HASH, __version__


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def git_info() -> tuple[str, bool]:
    root = repo_root()
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        )
        return head, dirty
    except (OSError, subprocess.SubprocessError):
        return "unknown", True


def lock_sha256() -> str | None:
    lock = repo_root() / "uv.lock"
    if not lock.is_file():
        return None
    return "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()


def software_block() -> dict[str, Any]:
    commit, dirty = git_info()
    return {
        "jcheng_learning": __version__,
        "git_commit": commit,
        "git_dirty": dirty,
        "contract_hash": CONTRACT_HASH,
        "python": platform.python_version(),
        "lock_sha256": lock_sha256(),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
