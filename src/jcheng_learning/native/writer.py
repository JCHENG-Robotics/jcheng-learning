"""Writer for the immutable JCHENG native episode store (``jcheng.dataset.v1``).

The writer is deliberately synchronous and single-threaded: deterministic
output matters more than throughput in M1. LeRobot is not imported here.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..errors import DatasetError
from ..io.hashing import root_hash, write_sha256sums
from ..io.image import write_rgb
from ..io.jsonl import write_jsonl
from ..io.yaml_io import write_yaml
from ..profiles import Profile
from ..version import CONTRACT_HASH, __version__

MANIFEST_SCHEMA = "jcheng.dataset.v1"
EPISODE_SCHEMA = "jcheng.episode.v1"
PROVENANCE_SCHEMA = "jcheng.provenance.v1"
SOURCE_CLASSES = {"synthetic", "simulation", "public-real", "own-real"}
TRUTHS = {"measured", "commanded", "unknown"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
_EPISODE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SI_UNITS = {"rad", "rad_s", "m", "m_s", "normalized"}


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _profile_sha256(profile: Profile) -> str:
    if profile.path is None:
        return "sha256:" + "0" * 64
    return _sha256_text(profile.path.read_text(encoding="utf-8"))


def _finite(values: list[float], where: str) -> list[float]:
    result = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise DatasetError(f"{where}: non-finite value {number!r}")
        result.append(number)
    return result


def _gripper_block(profile: Profile) -> dict[str, Any] | None:
    gripper = profile.gripper
    if gripper is None:
        return None
    block: dict[str, Any] = {"name": gripper.name, "space": gripper.space}
    if gripper.space in {"canonical", "linear"}:
        if gripper.closed is None or gripper.open is None:
            raise DatasetError("gripper: closed/open are required for this space")
        block["closed"] = float(gripper.closed)
        block["open"] = float(gripper.open)
    elif gripper.space == "normalized":
        block["range_known"] = gripper.range_known
        if gripper.range_known:
            if gripper.min is None or gripper.max is None:
                raise DatasetError("gripper: min/max are required when range_known")
            block["min"] = float(gripper.min)
            block["max"] = float(gripper.max)
    elif gripper.space == "raw_joint":
        if not gripper.raw_space:
            raise DatasetError("gripper: raw_space is required for raw_joint")
        block["raw_space"] = dict(gripper.raw_space)
    return block


class NativeDatasetWriter:
    """Write one dataset directory. The directory must not already exist."""

    def __init__(
        self,
        root: Path,
        dataset_id: str,
        source_class: str,
        profile: Profile,
        *,
        fps: int,
        created_at: str,
        clock_source: str = "monotonic",
        max_frame_jitter_ms: float = 10.0,
        max_camera_skew_ms: float = 50.0,
        state_truth: str = "measured",
        truth_source: str = "generator_truth",
        state_space_id: str | None = None,
        action_space_id: str | None = None,
        operator_session_id: str | None = None,
        capture: dict[str, Any] | None = None,
        calibration: list[dict[str, Any]] | None = None,
        license_block: dict[str, Any] | None = None,
        origin: dict[str, Any] | None = None,
        software: dict[str, Any] | None = None,
        upstream: dict[str, Any] | None = None,
        transformations: list[dict[str, Any]] | None = None,
        image_size: tuple[int, int] | None = None,
        include_images: bool = True,
    ) -> None:
        if not _ID_RE.match(dataset_id):
            raise DatasetError(f"invalid dataset_id: {dataset_id!r}")
        if source_class not in SOURCE_CLASSES:
            raise DatasetError(f"invalid source_class: {source_class!r}")
        if state_truth not in TRUTHS:
            raise DatasetError(f"invalid state truth: {state_truth!r}")
        if state_truth == "unknown" and source_class not in {"public-real", "simulation"}:
            raise DatasetError("state truth 'unknown' is only allowed for public imports")
        if not isinstance(fps, int) or fps < 1:
            raise DatasetError("fps must be a positive integer")
        try:
            datetime.fromisoformat(created_at)
        except ValueError as exc:
            raise DatasetError(f"created_at is not ISO 8601: {created_at!r}") from exc

        self.root = Path(root) / dataset_id
        if self.root.exists():
            raise DatasetError(f"dataset directory already exists: {self.root}")
        self.root.mkdir(parents=True)

        self.dataset_id = dataset_id
        self.source_class = source_class
        self.profile = profile
        self.fps = fps
        self.created_at = created_at
        self.clock_source = clock_source
        self.max_frame_jitter_ms = float(max_frame_jitter_ms)
        self.max_camera_skew_ms = float(max_camera_skew_ms)
        self.state_truth = state_truth
        self.truth_source = truth_source
        self.state_space = profile.state_space(state_space_id)
        self.action_space = profile.action_space(action_space_id)
        self.operator_session_id = operator_session_id
        self.capture = capture
        self.calibration = calibration or []
        self.license_block = license_block
        self.origin = origin
        self.software = software
        self.upstream = upstream
        self.transformations = transformations or []
        self.include_images = bool(include_images)

        self._camera_size = {
            camera.key: (
                int(image_size[0]) if image_size else camera.width,
                int(image_size[1]) if image_size else camera.height,
            )
            for camera in profile.cameras
        }
        self._episodes: list[dict[str, Any]] = []
        self._tasks: list[str] = []
        self._current: dict[str, Any] | None = None
        self._last_t_ns: int | None = None
        self._finalized = False

    # ---------------------------------------------------------------- episodes
    def begin_episode(
        self,
        episode_id: str,
        task: str,
        *,
        outcome: str = "unknown",
        start_ns: int = 0,
        labels: list[dict[str, Any]] | None = None,
    ) -> None:
        if self._current is not None:
            raise DatasetError("begin_episode called before end_episode")
        if not _EPISODE_RE.match(episode_id):
            raise DatasetError(f"invalid episode_id: {episode_id!r}")
        if not task:
            raise DatasetError("episode task must not be empty")
        if outcome not in {"success", "failure", "unknown", "aborted"}:
            raise DatasetError(f"invalid episode outcome: {outcome!r}")
        self._current = {
            "id": episode_id,
            "task": task,
            "outcome": outcome,
            "start_ns": int(start_ns),
            "labels": labels or [],
            "frames": [],
            "dir": self.root / "episodes" / episode_id,
        }
        self._current["dir"].mkdir(parents=True, exist_ok=False)
        self._last_t_ns = None

    def add_frame(
        self,
        *,
        t_ns: int,
        state: list[float] | np.ndarray,
        action: list[float] | np.ndarray,
        images: dict[str, tuple[np.ndarray, int]] | None = None,
        truth: str | None = None,
        task: str | None = None,
        valid: bool = True,
        flags: list[str] | None = None,
    ) -> None:
        if self._current is None:
            raise DatasetError("add_frame called outside an episode")
        t_ns = int(t_ns)
        if t_ns < 0:
            raise DatasetError("t_ns must be non-negative")
        if self._last_t_ns is not None and t_ns < self._last_t_ns:
            raise DatasetError("t_ns must be monotonic within an episode")

        state = _finite([float(v) for v in np.asarray(state).reshape(-1)], "state")
        action = _finite([float(v) for v in np.asarray(action).reshape(-1)], "action")
        if len(state) != len(self.state_space.names):
            raise DatasetError(
                f"state has {len(state)} values, expected {len(self.state_space.names)}"
            )
        if len(action) != len(self.action_space.names):
            raise DatasetError(
                f"action has {len(action)} values, expected {len(self.action_space.names)}"
            )
        frame_truth = truth or self.state_truth
        if frame_truth not in TRUTHS:
            raise DatasetError(f"invalid frame truth: {frame_truth!r}")
        if self.state_truth != "unknown" and frame_truth != self.state_truth:
            raise DatasetError(
                f"frame truth {frame_truth!r} does not match dataset truth {self.state_truth!r}"
            )

        frame_index = len(self._current["frames"])
        image_records: dict[str, dict[str, Any]] = {}
        images = images or {}
        if not self.include_images:
            images = {}
        for camera in (self.profile.cameras if self.include_images else ()):
            entry = images.get(camera.key)
            if entry is None:
                if camera.required:
                    raise DatasetError(f"missing required camera {camera.key!r}")
                continue
            pixels, stamp_ns = entry
            array = np.asarray(pixels)
            width, height = self._camera_size[camera.key]
            if array.shape != (height, width, 3) or array.dtype != np.uint8:
                raise DatasetError(
                    f"camera {camera.key!r}: expected uint8 ({height},{width},3), "
                    f"got {array.dtype} {array.shape}"
                )
            rel = f"images/{camera.key}/{frame_index:06d}.png"
            write_rgb(self._current["dir"] / rel, array)
            image_records[camera.key] = {
                "path": rel,
                "stamp_ns": int(stamp_ns),
                "width": width,
                "height": height,
                "encoding": "rgb8",
            }
        unknown = sorted(set(images) - {c.key for c in self.profile.cameras})
        if unknown:
            raise DatasetError(f"unknown cameras: {unknown}")

        record: dict[str, Any] = {
            "frame_index": frame_index,
            "t_ns": t_ns,
            "observation": {
                "state": state,
                "truth": frame_truth,
                "images": image_records,
            },
            "action": {
                "kind": "joint_position_absolute",
                "space_id": self.action_space.id,
                "values": action,
            },
            "valid": bool(valid),
            "flags": list(flags or []),
        }
        if task is not None:
            if task not in self._tasks and task != self._current["task"]:
                raise DatasetError(f"frame task {task!r} is not declared by the episode")
            record["task"] = task
        self._current["frames"].append(record)
        self._last_t_ns = t_ns

    def end_episode(self) -> None:
        if self._current is None:
            raise DatasetError("end_episode called without begin_episode")
        frames = self._current["frames"]
        if len(frames) < 2:
            raise DatasetError("an episode must have at least 2 frames")
        episode_dir = self._current["dir"]
        meta = {
            "schema": EPISODE_SCHEMA,
            "episode_id": self._current["id"],
            "start_ns": int(self._current["start_ns"]),
            "end_ns": int(frames[-1]["t_ns"] + round(1e9 / self.fps)),
            "nominal_fps": self.fps,
            "task": self._current["task"],
            "outcome": self._current["outcome"],
            "operator_session_id": self.operator_session_id,
            "capture": {
                "method": (self.capture or {}).get("method", "generator"),
                "tool": "jcheng-dataset",
                "version": __version__,
            },
            "frames": len(frames),
            "labels": self._current["labels"],
        }
        (episode_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_jsonl(episode_dir / "frames.jsonl", frames)
        if self._current["task"] not in self._tasks:
            self._tasks.append(self._current["task"])
        self._episodes.append(
            {
                "id": self._current["id"],
                "frames": len(frames),
                "duration_s": len(frames) / self.fps,
                "task": self._current["task"],
                "outcome": self._current["outcome"],
            }
        )
        self._current = None
        self._last_t_ns = None

    # ---------------------------------------------------------------- finalize
    def _state_block(self) -> dict[str, Any]:
        return {
            "space_id": self.state_space.id,
            "names": list(self.state_space.names),
            "units": list(self.state_space.units),
            "truth": self.state_truth,
            "truth_source": self.truth_source,
            "si_conformant": set(self.state_space.units) <= _SI_UNITS,
        }

    def _action_block(self) -> dict[str, Any]:
        block = {
            "space_id": self.action_space.id,
            "kind": "joint_position_absolute",
            "names": list(self.action_space.names),
            "units": list(self.action_space.units),
            "si_conformant": set(self.action_space.units) <= _SI_UNITS,
        }
        gripper = _gripper_block(self.profile)
        if gripper is not None:
            block["gripper"] = gripper
        return block

    def _manifest(self) -> dict[str, Any]:
        cameras = [
            {
                "key": camera.key,
                "width": self._camera_size[camera.key][0],
                "height": self._camera_size[camera.key][1],
                "encoding": "rgb8",
                "frame_id": camera.frame_id,
            }
            for camera in (self.profile.cameras if self.include_images else ())
        ]
        streams: list[dict[str, Any]] = [
            {"id": "state", "kind": "joint_state", "rate_hz": self.fps, "required": True}
        ]
        for camera in (self.profile.cameras if self.include_images else ()):
            streams.append(
                {
                    "id": f"camera.{camera.key}",
                    "kind": "image",
                    "rate_hz": camera.rate_hz,
                    "required": camera.required,
                    "camera_key": camera.key,
                }
            )
        return {
            "schema": MANIFEST_SCHEMA,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at,
            "source_class": self.source_class,
            "robot": {
                "adapter_id": self.profile.id,
                "adapter_version": self.profile.version,
                "adapter_sha256": _profile_sha256(self.profile),
                "dof": self.profile.dof,
                "has_gripper": self.profile.has_gripper,
            },
            "state": self._state_block(),
            "action": self._action_block(),
            "timing": {
                "nominal_fps": self.fps,
                "clock_source": self.clock_source,
                "time_unit": "ns",
                "max_frame_jitter_ms": self.max_frame_jitter_ms,
                "max_camera_skew_ms": self.max_camera_skew_ms,
            },
            "streams": streams,
            "cameras": cameras,
            "episodes": self._episodes,
            "tasks": self._tasks,
        }

    def _provenance(self) -> dict[str, Any]:
        software = {
            "jcheng_learning": __version__,
            "contract_hash": CONTRACT_HASH,
            "python": platform.python_version(),
        }
        if self.software:
            software.update(self.software)
        capture = self.capture or {
            "method": "generator",
            "operator_session_id": self.operator_session_id,
            "authorization_ref": None,
            "started_at": self.created_at,
            "ended_at": self.created_at,
        }
        return {
            "schema": PROVENANCE_SCHEMA,
            "dataset_id": self.dataset_id,
            "source_class": self.source_class,
            "origin": self.origin or {"kind": "generator", "public": False},
            "robot": {
                "adapter_id": self.profile.id,
                "adapter_sha256": _profile_sha256(self.profile),
            },
            "software": software,
            "capture": capture,
            "calibration": self.calibration,
            "license": self.license_block
            or {"dataset": "internal", "consent": None, "redistribution": "none"},
            "upstream": self.upstream,
            "transformations": self.transformations,
        }

    def finalize(self) -> str:
        if self._current is not None:
            raise DatasetError("cannot finalize with an open episode")
        if self._finalized:
            return root_hash(self.root)
        if not self._episodes:
            raise DatasetError("cannot finalize a dataset without episodes")
        write_yaml(self.root / "dataset.yaml", self._manifest())
        (self.root / "provenance.json").write_text(
            json.dumps(self._provenance(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_sha256sums(self.root)
        self._finalized = True
        return root_hash(self.root)
