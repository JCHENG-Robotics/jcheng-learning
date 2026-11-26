"""Line-oriented JSONL reader/writer with ``file:line`` diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from ..errors import DatasetError


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"missing JSONL file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            text = line.rstrip("\n")
            if not text:
                raise DatasetError(f"{path}:{number}: empty line")
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{path}:{number}: {exc}") from exc
            if not isinstance(obj, dict):
                raise DatasetError(f"{path}:{number}: expected a JSON object")
            yield number, obj


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
