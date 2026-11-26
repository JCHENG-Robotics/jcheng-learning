"""YAML helpers with a stable, explicit error type."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..errors import DatasetError


def load_yaml(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"missing YAML file: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DatasetError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DatasetError(f"{path}: expected a YAML mapping")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
