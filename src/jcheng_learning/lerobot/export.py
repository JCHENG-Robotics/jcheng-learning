"""Export a native dataset with the official LeRobot v3 writer.

The exporter never writes Parquet/MP4 itself. It calls
``LeRobotDataset.create/add_frame/save_episode/finalize`` from the pinned
``lerobot`` package (an optional dependency).
"""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..errors import DatasetError, DependencyError
from ..io.hashing import file_sha256, root_hash
from ..native import NativeDatasetReader
from ..profiles import load_profile
from ..validate import validate_dataset
from .features import feature_map, feature_rename_map


@dataclass(frozen=True)
class ExportResult:
    root: Path
    dataset_id: str
    episodes: int
    frames: int
    dropped_frames: int
    lerobot_version: str


def _lerobot():
    try:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
    except ImportError as exc:  # pragma: no cover - exercised by compat job
        raise DependencyError(
            "lerobot[dataset]==0.7.0 is required for export; install the lerobot extra"
        ) from exc
    return LeRobotDataset


def _lerobot_version() -> str:
    try:
        return importlib.metadata.version("lerobot")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def export_native_dataset(
    source: Path,
    out: Path,
    *,
    mode: str = "images",
    include_images: bool = True,
    sample_policy: str = "strict",
) -> ExportResult:
    if sample_policy != "strict":
        raise DatasetError("only --sample-policy strict is implemented")
    reader = NativeDatasetReader(source)
    manifest = reader.manifest
    profile = load_profile(str(manifest["robot"]["adapter_id"]))
    fps = int(manifest["timing"]["nominal_fps"])
    out = Path(out)
    if out.exists():
        raise DatasetError(f"output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    cameras = list(manifest.get("cameras", [])) if include_images else []
    if include_images and not cameras:
        raise DatasetError("dataset has no declared cameras; use --no-images")
    features = feature_map(
        profile, cameras=cameras, include_images=include_images, mode=mode
    )
    LeRobotDataset = _lerobot()

    tmp_parent = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    tmp_root = tmp_parent / "lerobot"
    try:
        ds = LeRobotDataset.create(
            repo_id=f"local/{reader.dataset_id}",
            fps=fps,
            features=features,
            root=tmp_root,
            robot_type=profile.id,
            use_videos=(mode == "videos"),
        )
        dropped = 0
        exported_frames = 0
        native_frames = sum(len(episode.frames) for episode in reader.episodes())
        for episode in reader.episodes():
            episode_frames = 0
            for frame_index, frame in enumerate(episode.frames):
                if not frame.get("valid", True):
                    dropped += 1
                    continue
                row: dict[str, Any] = {
                    "observation.state": np.asarray(
                        frame["observation"]["state"], dtype=np.float32
                    ),
                    "action": np.asarray(frame["action"]["values"], dtype=np.float32),
                    "task": episode.meta["task"],
                }
                if include_images:
                    for camera in cameras:
                        key = str(camera["key"])
                        row[f"observation.images.{key}"] = episode.image(
                            frame_index, key
                        )
                ds.add_frame(row)
                episode_frames += 1
                exported_frames += 1
            if episode_frames < 2:
                raise DatasetError(f"episode {episode.episode_id} has <2 exported frames")
            ds.save_episode()
        ds.finalize()

        info_path = tmp_root / "meta" / "info.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        if int(info.get("total_episodes", -1)) != len(reader.manifest["episodes"]):
            raise DatasetError("LeRobot episode count does not match the native dataset")
        if int(info.get("total_frames", -1)) != exported_frames:
            raise DatasetError("LeRobot frame count does not match the export")

        sidecar = tmp_root / "jcheng"
        sidecar.mkdir()
        (sidecar / "provenance.json").write_text(
            (source / "provenance.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        report = validate_dataset(source).to_dict()
        (sidecar / "quality.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        export_record = {
            "schema": "jcheng.lerobot-export.v1",
            "lerobot_version": _lerobot_version(),
            "codebase_version": info.get("codebase_version"),
            "source": {
                "dataset_id": reader.dataset_id,
                "root_sha256": "sha256:" + root_hash(source),
            },
            "fps": fps,
            "mode": mode,
            "include_images": include_images,
            "sample_policy": sample_policy,
            "dropped_frames": dropped,
            "time_compression": (
                exported_frames / native_frames if native_frames else 0.0
            ),
            "feature_map": feature_rename_map(features),
        }
        (sidecar / "export.json").write_text(
            json.dumps(export_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (sidecar / "info.sha256").write_text(
            file_sha256(info_path) + "  meta/info.json\n", encoding="utf-8"
        )
        tmp_root.rename(out)
        return ExportResult(
            root=out,
            dataset_id=reader.dataset_id,
            episodes=len(reader.manifest["episodes"]),
            frames=exported_frames,
            dropped_frames=dropped,
            lerobot_version=_lerobot_version(),
        )
    finally:
        if tmp_parent.exists():
            shutil.rmtree(tmp_parent, ignore_errors=True)
