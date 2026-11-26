"""Read-only reader for LeRobot Dataset v3.0 without importing torch.

Only ``pyarrow`` is used for Parquet. Image bytes embedded by the official
writer are returned as bytes; video decoding is deliberately out of scope here
and is handled by the optional ``[video]`` extra in a later stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from ..errors import DatasetError, InconclusiveError

CODEBASE_VERSION = "v3.0"


@dataclass(frozen=True)
class ForeignFrame:
    index: int
    episode_index: int
    frame_index: int
    timestamp: float
    state: tuple[float, ...]
    action: tuple[float, ...]
    images: dict[str, bytes]


@dataclass(frozen=True)
class ForeignEpisode:
    episode_index: int
    length: int
    tasks: tuple[str, ...]
    frames: tuple[ForeignFrame, ...]


def _names(feature: dict[str, Any]) -> tuple[str, ...]:
    names = feature.get("names")
    if isinstance(names, list):
        return tuple(str(name) for name in names)
    if isinstance(names, dict):
        flat: list[str] = []
        for value in names.values():
            flat.extend(str(name) for name in value)
        return tuple(flat)
    return ()


def _camera_key(feature_key: str) -> str:
    if feature_key == "observation.image":
        return "image"
    prefix = "observation.images."
    if feature_key.startswith(prefix):
        return feature_key[len(prefix) :]
    return feature_key


class LeRobotV3Reader:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        info_path = self.root / "meta" / "info.json"
        if not info_path.is_file():
            raise DatasetError(f"not a LeRobot dataset root: {self.root}")
        try:
            self.info = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{info_path}: {exc}") from exc
        if self.info.get("codebase_version") != CODEBASE_VERSION:
            raise InconclusiveError(
                f"unsupported LeRobot dataset version {self.info.get('codebase_version')!r}; "
                f"only {CODEBASE_VERSION} is supported"
            )
        self.fps = int(self.info["fps"])
        self.features: dict[str, dict[str, Any]] = self.info.get("features", {})
        self.total_episodes = int(self.info.get("total_episodes", 0))
        self.total_frames = int(self.info.get("total_frames", 0))
        self.robot_type = self.info.get("robot_type")
        self.state_names = _names(self.features.get("observation.state", {}))
        self.action_names = _names(self.features.get("action", {}))
        self.image_keys = [
            key
            for key, feature in self.features.items()
            if feature.get("dtype") == "image"
        ]
        self.video_keys = [
            key
            for key, feature in self.features.items()
            if feature.get("dtype") == "video"
        ]
        self._table: pa.Table | None = None
        self._tasks: dict[int, str] | None = None

    # ------------------------------------------------------------------ tasks
    def tasks(self) -> dict[int, str]:
        if self._tasks is not None:
            return self._tasks
        path = self.root / "meta" / "tasks.parquet"
        if not path.is_file():
            self._tasks = {}
            return self._tasks
        table = pq.read_table(path)
        data = table.to_pydict()
        index_column = data.get("task_index")
        if index_column is None:
            raise DatasetError(f"{path}: missing task_index column")
        text_column = next(
            (name for name in data if name != "task_index" and isinstance(data[name], list)),
            None,
        )
        if text_column is None:
            raise DatasetError(f"{path}: no task text column")
        self._tasks = {
            int(index): str(text)
            for index, text in zip(index_column, data[text_column])
        }
        return self._tasks

    # ---------------------------------------------------------------- frames
    def _data_table(self) -> pa.Table:
        if self._table is not None:
            return self._table
        files = sorted((self.root / "data").rglob("*.parquet"))
        if not files:
            raise DatasetError(f"{self.root}: no data/*.parquet files")
        tables = [pq.read_table(path) for path in files]
        table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]
        if "index" not in table.column_names:
            raise DatasetError("data table has no index column")
        table = table.sort_by("index")
        indexes = table.column("index").to_pylist()
        if indexes != list(range(len(indexes))):
            raise DatasetError("data index is not contiguous 0..N-1")
        self._table = table
        return table

    def _episode_rows(self) -> list[dict[str, Any]]:
        files = sorted((self.root / "meta" / "episodes").rglob("*.parquet"))
        if not files:
            raise DatasetError(f"{self.root}: no meta/episodes/*.parquet files")
        tables = [pq.read_table(path) for path in files]
        table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]
        rows = table.to_pylist()
        rows.sort(key=lambda row: int(row["episode_index"]))
        return rows

    def episodes(self) -> Iterator[ForeignEpisode]:
        table = self._data_table()
        columns = table.to_pydict()
        tasks = self.tasks()
        rows = self._episode_rows()
        expected_start = 0
        for row in rows:
            episode_index = int(row["episode_index"])
            length = int(row["length"])
            start = int(row["dataset_from_index"])
            end = int(row["dataset_to_index"])
            if start != expected_start:
                raise DatasetError(f"episode {episode_index}: non-contiguous start {start}")
            if end - start != length:
                raise DatasetError(f"episode {episode_index}: length mismatch")
            expected_start = end
            episode_tasks = tuple(str(task) for task in (row.get("tasks") or ()))
            if not episode_tasks:
                first_task_index = int(columns["task_index"][start])
                episode_tasks = (tasks.get(first_task_index, ""),)
            frames: list[ForeignFrame] = []
            for global_index in range(start, end):
                if int(columns["index"][global_index]) != global_index:
                    raise DatasetError(f"episode {episode_index}: index mismatch")
                if int(columns["episode_index"][global_index]) != episode_index:
                    raise DatasetError(f"episode {episode_index}: episode_index mismatch")
                frame_index = int(columns["frame_index"][global_index])
                if frame_index != global_index - start:
                    raise DatasetError(f"episode {episode_index}: frame_index mismatch")
                images: dict[str, bytes] = {}
                for key in self.image_keys:
                    value = columns[key][global_index]
                    if isinstance(value, dict):
                        payload = value.get("bytes")
                        if payload is None and value.get("path"):
                            candidate = self.root / str(value["path"])
                            if candidate.is_file():
                                payload = candidate.read_bytes()
                        if payload is not None:
                            images[_camera_key(key)] = bytes(payload)
                frames.append(
                    ForeignFrame(
                        index=global_index,
                        episode_index=episode_index,
                        frame_index=frame_index,
                        timestamp=float(columns["timestamp"][global_index]),
                        state=tuple(float(v) for v in columns["observation.state"][global_index]),
                        action=tuple(float(v) for v in columns["action"][global_index]),
                        images=images,
                    )
                )
            yield ForeignEpisode(
                episode_index=episode_index,
                length=length,
                tasks=episode_tasks,
                frames=tuple(frames),
            )
