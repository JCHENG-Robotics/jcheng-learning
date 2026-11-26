"""Read-only access to a JCHENG native dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from ..errors import DatasetError
from ..io.hashing import root_hash, verify_sha256sums
from ..io.image import read_rgb
from ..io.jsonl import read_jsonl
from ..io.yaml_io import load_yaml


@dataclass(frozen=True)
class Episode:
    episode_id: str
    meta: dict[str, Any]
    frames: tuple[dict[str, Any], ...]
    directory: Path

    def image_path(self, frame_index: int, camera: str) -> Path:
        frame = self.frames[frame_index]
        try:
            rel = frame["observation"]["images"][camera]["path"]
        except KeyError as exc:
            raise DatasetError(
                f"episode {self.episode_id} frame {frame_index}: no camera {camera!r}"
            ) from exc
        return self.directory / rel

    def image(self, frame_index: int, camera: str) -> np.ndarray:
        return read_rgb(self.image_path(frame_index, camera))


class NativeDatasetReader:
    def __init__(self, root: Path, *, verify: bool = True) -> None:
        self.root = Path(root)
        if not (self.root / "dataset.yaml").is_file():
            raise DatasetError(f"not a native dataset root: {self.root}")
        self.manifest = load_yaml(self.root / "dataset.yaml")
        if self.manifest.get("schema") != "jcheng.dataset.v1":
            raise DatasetError(
                f"{self.root / 'dataset.yaml'}: unsupported schema "
                f"{self.manifest.get('schema')!r}"
            )
        provenance_path = self.root / "provenance.json"
        if not provenance_path.is_file():
            raise DatasetError(f"missing provenance.json: {self.root}")
        try:
            self.provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{provenance_path}: {exc}") from exc
        if self.provenance.get("schema") != "jcheng.provenance.v1":
            raise DatasetError(f"{provenance_path}: unsupported provenance schema")
        if verify:
            problems = verify_sha256sums(self.root)
            if problems:
                raise DatasetError(
                    "dataset integrity failure:\n" + "\n".join(problems)
                )

    @property
    def dataset_id(self) -> str:
        return str(self.manifest["dataset_id"])

    @property
    def root_hash(self) -> str:
        return root_hash(self.root)

    def episodes(self) -> Iterator[Episode]:
        episodes = self.manifest.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            raise DatasetError("manifest has no episodes")
        for entry in episodes:
            episode_id = str(entry["id"])
            directory = self.root / "episodes" / episode_id
            meta_path = directory / "meta.json"
            if not meta_path.is_file():
                raise DatasetError(f"missing episode metadata: {meta_path}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("schema") != "jcheng.episode.v1":
                raise DatasetError(f"{meta_path}: unsupported episode schema")
            frames = tuple(
                frame for _, frame in read_jsonl(directory / "frames.jsonl")
            )
            if len(frames) != int(meta["frames"]):
                raise DatasetError(
                    f"{episode_id}: {len(frames)} frames but meta says {meta['frames']}"
                )
            if len(frames) != int(entry["frames"]):
                raise DatasetError(
                    f"{episode_id}: {len(frames)} frames but manifest says {entry['frames']}"
                )
            previous_t = None
            for expected, frame in enumerate(frames):
                if frame.get("frame_index") != expected:
                    raise DatasetError(
                        f"{episode_id}: frame_index {frame.get('frame_index')} "
                        f"at line {expected + 1}, expected {expected}"
                    )
                t_ns = int(frame["t_ns"])
                if previous_t is not None and t_ns < previous_t:
                    raise DatasetError(f"{episode_id}: t_ns is not monotonic")
                previous_t = t_ns
            yield Episode(episode_id=episode_id, meta=meta, frames=frames, directory=directory)
