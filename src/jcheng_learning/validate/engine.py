"""Dataset integrity and quality checks (the M1 ``DQ-*`` gate).

The engine is deliberately tolerant: it keeps going after a failed check so a
single report lists every problem. It never repairs anything.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

import numpy as np

from ..errors import DatasetError
from ..io.hashing import read_sha256sums, root_hash, verify_sha256sums
from ..io.image import read_rgb
from ..io.jsonl import read_jsonl
from ..io.yaml_io import load_yaml
from ..native.writer import _profile_sha256
from ..profiles import Profile, load_profile
from ..version import __version__

SOURCE_CLASSES = {"synthetic", "simulation", "public-real", "own-real"}
TRUTH_SOURCES = {
    "synthetic": {"generator_truth"},
    "simulation": {"simulator_truth", "source_dataset"},
    "public-real": {"source_dataset", "unknown"},
    "own-real": {"bus_read", "command_cache"},
}
UNITS = {"rad", "rad_s", "m", "m_s", "normalized", "deg", "px", "pulse"}
SI_UNITS = {"rad", "rad_s", "m", "m_s", "normalized"}
SEVERITY = {
    "DQ-T04": "warning",
    "DQ-T07": "warning",
    "DQ-V03": "warning",
    "DQ-V04": "warning",
    "DQ-V05": "warning",
    "DQ-I06": "warning",
    "DQ-I08": "warning",
    "DQ-X02": "warning",
    "DQ-X05": "warning",
}


@dataclass
class Check:
    id: str
    severity: str
    status: str
    message: str = ""
    counts: dict[str, Any] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "counts": self.counts,
            "samples": self.samples,
        }


@dataclass
class Report:
    dataset: dict[str, Any]
    tool: dict[str, Any]
    run: dict[str, Any]
    summary: dict[str, Any]
    checks: list[Check]
    features: dict[str, Any]
    episodes: list[dict[str, Any]]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "jcheng.dataset-quality-report.v1",
            "dataset": self.dataset,
            "tool": self.tool,
            "run": self.run,
            "summary": self.summary,
            "checks": [check.to_dict() for check in sorted(self.checks, key=lambda c: c.id)],
            "features": self.features,
            "episodes": self.episodes,
            "limitations": self.limitations,
        }


def _check(
    checks: list[Check],
    check_id: str,
    status: str,
    message: str = "",
    counts: dict[str, Any] | None = None,
    samples: list[str] | None = None,
) -> None:
    checks.append(
        Check(
            id=check_id,
            severity=SEVERITY.get(check_id, "error"),
            status=status,
            message=message,
            counts=counts or {},
            samples=(samples or [])[:10],
        )
    )


def _has(mapping: Any, *keys: str) -> bool:
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return True


def _get(mapping: Any, *keys: str, default: Any = None) -> Any:
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _finite_list(values: Any) -> tuple[list[float], int]:
    if not isinstance(values, list):
        return [], 1
    result: list[float] = []
    bad = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            bad += 1
            continue
        number = float(value)
        if not math.isfinite(number):
            bad += 1
            continue
        result.append(number)
    return result, bad


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "min": float(array.min()),
        "max": float(array.max()),
        "mean": float(array.mean()),
        "std": float(array.std()),
        "q01": float(np.quantile(array, 0.01)),
        "q99": float(np.quantile(array, 0.99)),
    }


def _episode_digest(episode_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(episode_dir.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(episode_dir).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _aggregate_checks(checks: list[Check]) -> list[Check]:
    rank = {"pass": 0, "skip": 1, "inconclusive": 2, "fail": 3}
    aggregated: dict[str, Check] = {}
    for check in checks:
        current = aggregated.get(check.id)
        if current is None:
            aggregated[check.id] = Check(
                id=check.id,
                severity=check.severity,
                status=check.status,
                message=check.message,
                counts=dict(check.counts),
                samples=list(check.samples),
            )
            continue
        current.counts["occurrences"] = current.counts.get("occurrences", 1) + 1
        if rank[check.status] > rank[current.status]:
            current.status = check.status
            if check.message:
                current.message = check.message
        if check.severity == "error":
            current.severity = "error"
        for key, value in check.counts.items():
            if isinstance(value, (int, float)) and isinstance(current.counts.get(key), (int, float)):
                current.counts[key] += value
        for sample in check.samples:
            if len(current.samples) < 10 and sample not in current.samples:
                current.samples.append(sample)
    return list(aggregated.values())


class Validator:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.checks: list[Check] = []
        self.limitations: list[str] = []
        self.manifest: dict[str, Any] = {}
        self.provenance: dict[str, Any] = {}
        self.profile: Profile | None = None
        self.sums_ok = False
        self.feature_values: dict[str, list[float]] = {
            "observation.state": [],
            "action": [],
        }
        self.episodes: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ load
    def _load(self) -> bool:
        manifest_path = self.root / "dataset.yaml"
        if not manifest_path.is_file():
            _check(self.checks, "DQ-M01", "fail", f"missing {manifest_path}")
            return False
        try:
            self.manifest = load_yaml(manifest_path)
        except DatasetError as exc:
            _check(self.checks, "DQ-M01", "fail", str(exc))
            return False
        if self.manifest.get("schema") != "jcheng.dataset.v1":
            _check(self.checks, "DQ-M01", "fail", "unsupported dataset schema")
            return False

        required = (
            "dataset_id",
            "created_at",
            "source_class",
            "robot",
            "state",
            "action",
            "timing",
            "streams",
            "episodes",
            "tasks",
        )
        missing = [key for key in required if key not in self.manifest]
        if missing:
            _check(self.checks, "DQ-M01", "fail", f"missing manifest fields: {missing}")
            return False
        _check(self.checks, "DQ-M01", "pass")

        profile_id = _get(self.manifest, "robot", "adapter_id")
        try:
            self.profile = load_profile(str(profile_id))
            _check(self.checks, "DQ-M08", "pass")
        except DatasetError as exc:
            _check(self.checks, "DQ-M08", "fail", str(exc))

        provenance_path = self.root / "provenance.json"
        if not provenance_path.is_file():
            _check(self.checks, "DQ-M02", "fail", "missing provenance.json")
        else:
            try:
                self.provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                if self.provenance.get("schema") != "jcheng.provenance.v1":
                    raise DatasetError("unsupported provenance schema")
                _check(self.checks, "DQ-M02", "pass")
            except (json.JSONDecodeError, DatasetError) as exc:
                _check(self.checks, "DQ-M02", "fail", f"provenance.json: {exc}")

        self._check_sums()
        self._check_identity()
        self._check_layout()
        return True

    def _check_sums(self) -> None:
        sums_path = self.root / "SHA256SUMS"
        if not sums_path.is_file():
            _check(self.checks, "DQ-M04", "fail", "missing SHA256SUMS")
            return
        try:
            read_sha256sums(sums_path)
        except DatasetError as exc:
            _check(self.checks, "DQ-M04", "fail", str(exc))
            return
        problems = verify_sha256sums(self.root)
        if problems:
            _check(self.checks, "DQ-M04", "fail", "; ".join(problems), {"problems": len(problems)})
            missing = [p for p in problems if p.startswith("missing file:")]
            if missing:
                _check(self.checks, "DQ-M05", "fail", "; ".join(missing), {"missing": len(missing)})
            return
        self.sums_ok = True
        _check(self.checks, "DQ-M04", "pass")

    def _check_identity(self) -> None:
        dataset_id = str(self.manifest.get("dataset_id", ""))
        if not dataset_id or any(
            ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in dataset_id
        ):
            _check(self.checks, "DQ-M03", "fail", f"invalid dataset_id {dataset_id!r}")
        else:
            _check(self.checks, "DQ-M03", "pass")

    def _check_layout(self) -> None:
        problems: list[str] = []
        for path in self.root.rglob("*"):
            if path.is_symlink():
                problems.append(f"symlink: {path.relative_to(self.root)}")
        if problems:
            _check(self.checks, "DQ-M05", "fail", "; ".join(problems), {"symlinks": len(problems)})
        else:
            if not any(c.id == "DQ-M05" and c.status == "fail" for c in self.checks):
                _check(self.checks, "DQ-M05", "pass")
        episodes = self.manifest.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            _check(self.checks, "DQ-M06", "fail", "manifest episodes is empty")
            return
        ids = [str(item.get("id", "")) for item in episodes if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            _check(self.checks, "DQ-M07", "fail", "duplicate episode ids")
        else:
            _check(self.checks, "DQ-M07", "pass")
        total = 0
        for item in episodes:
            if not isinstance(item, dict) or "id" not in item or "frames" not in item:
                _check(self.checks, "DQ-M06", "fail", "episode entry is incomplete")
                return
            total += int(item["frames"])
        _check(self.checks, "DQ-M06", "pass", counts={"episodes": len(episodes), "frames": total})

    # -------------------------------------------------------------- episodes
    def _check_episode(self, entry: dict[str, Any]) -> None:
        episode_id = str(entry["id"])
        directory = self.root / "episodes" / episode_id
        meta_path = directory / "meta.json"
        frames_path = directory / "frames.jsonl"
        if not meta_path.is_file() or not frames_path.is_file():
            _check(
                self.checks,
                "DQ-M02",
                "fail",
                f"episode {episode_id}: missing meta.json/frames.jsonl",
            )
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _check(self.checks, "DQ-M02", "fail", f"{episode_id}: {exc}")
            return
        frames = [frame for _, frame in read_jsonl(frames_path)]
        if len(frames) != int(entry.get("frames", -1)):
            _check(
                self.checks,
                "DQ-M06",
                "fail",
                f"{episode_id}: {len(frames)} frames, manifest says {entry.get('frames')}",
            )
        if len(frames) != int(meta.get("frames", -1)):
            _check(
                self.checks,
                "DQ-M06",
                "fail",
                f"{episode_id}: {len(frames)} frames, meta says {meta.get('frames')}",
            )
        if len(frames) < 2 or len(frames) > 100000:
            _check(self.checks, "DQ-X06", "fail", f"{episode_id}: frame count {len(frames)}")
        else:
            _check(self.checks, "DQ-X06", "pass")

        task = meta.get("task")
        tasks = self.manifest.get("tasks", [])
        if not task or task not in tasks:
            _check(self.checks, "DQ-X05", "fail", f"{episode_id}: task {task!r} not in manifest")
        else:
            _check(self.checks, "DQ-X05", "pass")

        fps = int(_get(self.manifest, "timing", "nominal_fps", default=0) or 0)
        if fps > 0:
            expected = len(frames) / fps
            duration = float(entry.get("duration_s", 0.0))
            if abs(expected - duration) > max(0.01, 0.5 / fps):
                _check(
                    self.checks,
                    "DQ-T07",
                    "fail",
                    f"{episode_id}: duration {duration} != {expected}",
                )
            else:
                _check(self.checks, "DQ-T07", "pass")

        previous_t: int | None = None
        seen_t: set[int] = set()
        seen_stamps: dict[str, set[int]] = {}
        image_hashes: dict[str, set[str]] = {}
        jitter_max_ms = 0.0
        previous_action: list[float] | None = None
        profile = self.profile
        state_names = _get(self.manifest, "state", "names", default=[])
        action_names = _get(self.manifest, "action", "names", default=[])
        state_units = _get(self.manifest, "state", "units", default=[])
        action_units = _get(self.manifest, "action", "units", default=[])
        action_kind = _get(self.manifest, "action", "kind")
        action_space_id = _get(self.manifest, "action", "space_id")
        state_space_id = _get(self.manifest, "state", "space_id")
        truth = _get(self.manifest, "state", "truth")
        truth_source = _get(self.manifest, "state", "truth_source")
        source_class = self.manifest.get("source_class")
        gripper_space = _get(self.manifest, "action", "gripper", "space")
        max_skew_ns = int(float(_get(self.manifest, "timing", "max_camera_skew_ms", default=0)) * 1e6)
        manifest_cameras = {
            str(item["key"]): item
            for item in self.manifest.get("cameras", [])
            if isinstance(item, dict) and {"key", "width", "height"} <= set(item)
        }
        camera_sizes = {
            key: (int(item["width"]), int(item["height"]))
            for key, item in manifest_cameras.items()
        }
        frame_period_ns = round(1e9 / fps) if fps else 0

        if profile is not None and not profile.state_space().limits_known:
            _check(self.checks, "DQ-J03", "inconclusive", "profile limits are unknown")
            _check(self.checks, "DQ-V02", "inconclusive", "profile limits are unknown")
        if profile is not None:
            if list(state_names) != list(profile.state_space().names):
                _check(self.checks, "DQ-J02", "fail", "state names differ from profile")
            else:
                _check(self.checks, "DQ-J02", "pass")
            if list(action_names) != list(profile.action_space().names):
                _check(self.checks, "DQ-J02", "fail", "action names differ from profile")
            if action_space_id != profile.action_space().id:
                _check(self.checks, "DQ-J08", "fail", "action space id differs from profile")
            else:
                _check(self.checks, "DQ-J08", "pass")
            if state_space_id not in {space.id for space in profile.state_spaces}:
                _check(self.checks, "DQ-J09", "fail", "state space id is not in profile")
            elif action_space_id not in {space.id for space in profile.action_spaces}:
                _check(self.checks, "DQ-J09", "fail", "action space id is not in profile")
            else:
                _check(self.checks, "DQ-J09", "pass")
            if gripper_space != (profile.gripper.space if profile.gripper else None):
                _check(self.checks, "DQ-J06", "fail", "gripper space differs from profile")
            else:
                _check(self.checks, "DQ-J06", "pass")
            if profile.gripper is None:
                _check(self.checks, "DQ-J07", "skip", "profile has no gripper")
            elif not profile.gripper.range_known:
                _check(self.checks, "DQ-J07", "inconclusive", "gripper range is unknown")
        else:
            _check(self.checks, "DQ-J02", "inconclusive", "profile unavailable")
            _check(self.checks, "DQ-J08", "inconclusive", "profile unavailable")
            _check(self.checks, "DQ-J09", "inconclusive", "profile unavailable")
            _check(self.checks, "DQ-J06", "inconclusive", "profile unavailable")

        if action_kind != "joint_position_absolute":
            _check(self.checks, "DQ-J05", "fail", f"unsupported action kind {action_kind!r}")
        else:
            _check(self.checks, "DQ-J05", "pass")

        public_origin = bool(_get(self.provenance, "origin", "public", default=False))
        state_si = set(state_units) <= SI_UNITS
        action_si = set(action_units) <= SI_UNITS
        if len(state_units) != len(state_names) or any(unit not in UNITS for unit in state_units):
            _check(self.checks, "DQ-J04", "fail", "state units are invalid")
        elif source_class in {"synthetic", "simulation", "own-real"} and not public_origin and not state_si:
            _check(self.checks, "DQ-J04", "fail", "only public imports may use non-SI units")
        elif not state_si and _get(self.manifest, "state", "si_conformant", default=True):
            _check(self.checks, "DQ-J04", "fail", "non-SI units must set si_conformant: false")
        else:
            _check(self.checks, "DQ-J04", "pass")
        if len(action_units) != len(action_names) or any(unit not in UNITS for unit in action_units):
            _check(self.checks, "DQ-J04", "fail", "action units are invalid")
        elif source_class in {"synthetic", "simulation", "own-real"} and not public_origin and not action_si:
            _check(self.checks, "DQ-J04", "fail", "only public imports may use non-SI units")
        elif not action_si and _get(self.manifest, "action", "si_conformant", default=True):
            _check(self.checks, "DQ-J04", "fail", "non-SI action units must set si_conformant: false")

        clock_source = _get(self.manifest, "timing", "clock_source")
        time_unit = _get(self.manifest, "timing", "time_unit")
        if clock_source not in {"monotonic", "ros_time", "system", "lerobot"}:
            _check(self.checks, "DQ-T08", "fail", f"invalid clock_source {clock_source!r}")
        elif time_unit != "ns":
            _check(self.checks, "DQ-T08", "fail", f"invalid time_unit {time_unit!r}")
        elif fps < 1:
            _check(self.checks, "DQ-T08", "fail", "invalid nominal_fps")
        else:
            _check(self.checks, "DQ-T08", "pass")

        for expected, frame in enumerate(frames):
            where = f"{episode_id}:{expected}"
            if frame.get("frame_index") != expected:
                _check(self.checks, "DQ-T03", "fail", f"{where}: bad frame_index")
            t_ns = frame.get("t_ns")
            if not isinstance(t_ns, int) or isinstance(t_ns, bool) or t_ns < 0:
                _check(self.checks, "DQ-T01", "fail", f"{where}: bad t_ns")
                t_ns = None
            else:
                if previous_t is not None:
                    if t_ns < previous_t:
                        _check(self.checks, "DQ-T02", "fail", f"{where}: t_ns regressed")
                    if frame_period_ns:
                        jitter_max_ms = max(
                            jitter_max_ms,
                            abs((t_ns - previous_t) - frame_period_ns) / 1e6,
                        )
                if t_ns in seen_t:
                    _check(self.checks, "DQ-T05", "fail", f"{where}: duplicate state timestamp")
                seen_t.add(t_ns)
                previous_t = t_ns

            state, bad_state = _finite_list(_get(frame, "observation", "state"))
            action, bad_action = _finite_list(_get(frame, "action", "values"))
            if bad_state or bad_action:
                _check(self.checks, "DQ-V01", "fail", f"{where}: NaN/Inf or non-numeric")
            if len(state) != len(state_names):
                _check(self.checks, "DQ-J01", "fail", f"{where}: state dimension")
            if len(action) != len(action_names):
                _check(self.checks, "DQ-J01", "fail", f"{where}: action dimension")
            self.feature_values["observation.state"].extend(state)
            self.feature_values["action"].extend(action)

            frame_truth = _get(frame, "observation", "truth")
            if frame_truth not in {"measured", "commanded", "unknown"}:
                _check(self.checks, "DQ-P07", "fail", f"{where}: invalid truth")
            elif truth not in {"measured", "commanded", "unknown"}:
                _check(self.checks, "DQ-P07", "fail", "manifest truth is invalid")
            elif truth != "unknown" and frame_truth != truth:
                _check(self.checks, "DQ-P07", "fail", f"{where}: truth differs from manifest")

            if profile is not None and len(state) == len(profile.state_space().names):
                for name, value in zip(profile.state_space().names, state):
                    joint = next((j for j in profile.joints if j.name == name), None)
                    if joint is None:
                        continue
                    if not profile.state_space().limits_known:
                        continue
                    if joint.lower is not None and joint.upper is not None:
                        if value < joint.lower - 1e-6 or value > joint.upper + 1e-6:
                            _check(
                                self.checks,
                                "DQ-J03",
                                "fail",
                                f"{where}: {name}={value} outside profile limits",
                            )
                            _check(self.checks, "DQ-V02", "fail", f"{where}: magnitude")
                            break
                for name, value in zip(profile.action_space().names, action):
                    joint = next((j for j in profile.joints if j.name == name), None)
                    if joint is None or joint.lower is None or joint.upper is None:
                        continue
                    if value < joint.lower - 1e-6 or value > joint.upper + 1e-6:
                        _check(
                            self.checks,
                            "DQ-J03",
                            "fail",
                            f"{where}: action {name}={value} outside profile limits",
                        )
                        break

            if profile is not None and profile.gripper is not None and profile.gripper.range_known:
                gripper = profile.gripper
                if gripper.space in {"canonical", "linear"}:
                    low, high = sorted((float(gripper.closed), float(gripper.open)))
                elif gripper.space == "raw_joint":
                    raw = gripper.raw_space or {}
                    low, high = float(raw.get("lower")), float(raw.get("upper"))
                else:
                    low = float(gripper.min) if gripper.min is not None else None
                    high = float(gripper.max) if gripper.max is not None else None
                if low is not None and high is not None and len(action) == len(action_names):
                    value = action[gripper.index]
                    if value < low - 1e-6 or value > high + 1e-6:
                        _check(
                            self.checks,
                            "DQ-J07",
                            "fail",
                            f"{where}: gripper={value} outside [{low}, {high}]",
                        )

            if previous_action is not None and len(action) == len(previous_action):
                gripper_index = profile.gripper.index if profile and profile.gripper else None
                for index, (old, new) in enumerate(zip(previous_action, action)):
                    if index == gripper_index:
                        continue
                    threshold = 1.0
                    if profile is not None and index < len(profile.joints):
                        joint = profile.joints[index]
                        if joint.lower is None or joint.upper is None:
                            continue
                        threshold = 0.5 * (joint.upper - joint.lower)
                    elif index < len(action_units):
                        if action_units[index] == "px":
                            threshold = 256.0
                        elif action_units[index] == "deg":
                            threshold = 90.0
                    if abs(new - old) > threshold:
                        _check(self.checks, "DQ-V06", "fail", f"{where}: action jump on dim {index}")
                        break
            previous_action = action

            images = _get(frame, "observation", "images", default={})
            if not isinstance(images, dict):
                _check(self.checks, "DQ-I01", "fail", f"{where}: images is not an object")
                images = {}
            for camera_key, camera_info in manifest_cameras.items():
                record = images.get(camera_key)
                if record is None:
                    _check(
                        self.checks,
                        "DQ-I01",
                        "fail",
                        f"{where}: missing camera {camera_key}",
                    )
                    continue
                path_value = record.get("path")
                if not isinstance(path_value, str) or path_value.startswith("/"):
                    _check(self.checks, "DQ-M05", "fail", f"{where}: absolute image path")
                    continue
                path = directory / path_value
                if not path.is_file():
                    _check(self.checks, "DQ-I02", "fail", f"{where}: missing {path_value}")
                    continue
                if path.stat().st_size == 0:
                    _check(self.checks, "DQ-I02", "fail", f"{where}: empty {path_value}")
                    continue
                try:
                    pixels = read_rgb(path)
                except DatasetError as exc:
                    _check(self.checks, "DQ-I03", "fail", f"{where}: {exc}")
                    continue
                width, height = camera_sizes[camera_key]
                if pixels.shape != (height, width, 3):
                    _check(
                        self.checks,
                        "DQ-I04",
                        "fail",
                        f"{where}: {camera_key} shape {pixels.shape}, expected {(height, width, 3)}",
                    )
                if pixels.dtype != np.uint8:
                    _check(self.checks, "DQ-I05", "fail", f"{where}: {camera_key} dtype")
                if float(pixels.var()) == 0.0:
                    _check(self.checks, "DQ-I06", "fail", f"{where}: {camera_key} blank")
                stamp = record.get("stamp_ns")
                if not isinstance(stamp, int) or isinstance(stamp, bool):
                    _check(self.checks, "DQ-I07", "fail", f"{where}: missing camera stamp")
                else:
                    if stamp in seen_stamps.setdefault(camera_key, set()):
                        _check(self.checks, "DQ-T05", "fail", f"{where}: duplicate camera stamp")
                    seen_stamps[camera_key].add(stamp)
                    if t_ns is not None and abs(stamp - t_ns) > max_skew_ns:
                        _check(self.checks, "DQ-T06", "fail", f"{where}: camera skew")
                digest = hashlib.sha256(pixels.tobytes()).hexdigest()
                if digest in image_hashes.setdefault(camera_key, set()):
                    _check(self.checks, "DQ-I08", "fail", f"{where}: duplicate image")
                image_hashes[camera_key].add(digest)

        if jitter_max_ms > float(_get(self.manifest, "timing", "max_frame_jitter_ms", default=0)):
            _check(
                self.checks,
                "DQ-T04",
                "fail",
                f"{episode_id}: jitter {jitter_max_ms:.3f} ms",
            )
        else:
            _check(self.checks, "DQ-T04", "pass", counts={"max_jitter_ms": jitter_max_ms})

        self.episodes.append(
            {
                "id": episode_id,
                "frames": len(frames),
                "duration_s": len(frames) / fps if fps else None,
                "images": sum(
                    len(_get(frame, "observation", "images", default={}) or {})
                    for frame in frames
                ),
                "digest": _episode_digest(directory) if directory.is_dir() else "",
            }
        )

    # ------------------------------------------------------------ provenance
    def _check_provenance(self) -> None:
        prov = self.provenance
        source_class = self.manifest.get("source_class")
        if source_class not in SOURCE_CLASSES:
            _check(self.checks, "DQ-P01", "fail", f"invalid source_class {source_class!r}")
        else:
            _check(self.checks, "DQ-P01", "pass")
        if not prov:
            _check(self.checks, "DQ-P02", "fail", "provenance missing")
            return
        if prov.get("source_class") != source_class:
            _check(self.checks, "DQ-P02", "fail", "provenance source_class differs from manifest")
        truth_source = _get(self.manifest, "state", "truth_source")
        if truth_source not in TRUTH_SOURCES.get(source_class, set()):
            _check(self.checks, "DQ-P07", "fail", f"truth_source {truth_source!r} invalid")
        else:
            _check(self.checks, "DQ-P07", "pass")

        if source_class == "synthetic":
            if not _has(prov, "origin", "generator", "name"):
                _check(self.checks, "DQ-P02", "fail", "synthetic provenance lacks generator")
        elif source_class == "simulation":
            if not _has(prov, "origin", "simulator"):
                _check(self.checks, "DQ-P02", "fail", "simulation provenance lacks simulator")
        elif source_class == "public-real":
            if not _has(prov, "upstream", "repo_id") or not _has(prov, "upstream", "revision"):
                _check(self.checks, "DQ-P02", "fail", "public provenance lacks repo_id/revision")
        elif source_class == "own-real":
            if not _get(prov, "capture", "operator_session_id"):
                _check(self.checks, "DQ-P05", "fail", "own-real lacks operator_session_id")
            if not _get(prov, "capture", "authorization_ref"):
                _check(self.checks, "DQ-P05", "fail", "own-real lacks authorization_ref")
            if not prov.get("calibration"):
                _check(self.checks, "DQ-P02", "fail", "own-real lacks calibration")
        else:
            _check(self.checks, "DQ-P02", "skip", "unknown source class")

        if source_class != "own-real":
            _check(self.checks, "DQ-P05", "skip", "not own-real")

        if source_class in {"public-real", "own-real"}:
            license_data = _get(prov, "license", "dataset")
            if license_data in {None, "", "internal", "unset"}:
                _check(self.checks, "DQ-P04", "fail", "license is not recorded")
            else:
                _check(self.checks, "DQ-P04", "pass")
        else:
            _check(self.checks, "DQ-P04", "skip", "internal synthetic/simulation data")

        software = prov.get("software", {})
        required = ("jcheng_learning", "git_commit", "contract_hash", "lock_sha256")
        missing = [key for key in required if not software.get(key)]
        if missing:
            _check(self.checks, "DQ-P06", "fail", f"software fields missing: {missing}")
        else:
            _check(self.checks, "DQ-P06", "pass")

        transformations = prov.get("transformations", [])
        if not isinstance(transformations, list):
            _check(self.checks, "DQ-P03", "fail", "transformations is not a list")
        else:
            _check(self.checks, "DQ-P03", "pass", counts={"entries": len(transformations)})

        if source_class == "own-real" and _get(self.manifest, "state", "truth_source") == "bus_read":
            if not any(
                (self.root / "episodes" / e["id"] / "measurements.jsonl").is_file()
                for e in self.manifest.get("episodes", [])
            ):
                _check(self.checks, "DQ-P02", "fail", "bus_read without measurements.jsonl")

    # ----------------------------------------------------------------- cross
    def _check_cross(self) -> None:
        digests = [episode["digest"] for episode in self.episodes if episode.get("digest")]
        if len(digests) != len(set(digests)):
            _check(self.checks, "DQ-X02", "fail", "duplicate episode content")
        else:
            _check(self.checks, "DQ-X02", "pass")
        _check(self.checks, "DQ-X01", "skip", "no split declaration in v1")
        _check(self.checks, "DQ-X03", "skip", "no declared aggregate stats in v1")
        _check(self.checks, "DQ-X04", "skip", "export round-trip is a separate check")

    def _check_features(self) -> None:
        for key, values in self.feature_values.items():
            self.feature_values[key] = values
        state = self.feature_values["observation.state"]
        action = self.feature_values["action"]
        if state and action:
            if all(abs(value) < 1e-12 for value in state):
                _check(self.checks, "DQ-V03", "fail", "state is constant zero")
            else:
                _check(self.checks, "DQ-V03", "pass")
            # A cheap outlier check over the whole dataset.
            array = np.asarray(action)
            if array.size > 1 and array.std() > 0:
                z = np.abs((array - array.mean()) / array.std())
                if float(z.max()) > 8:
                    _check(self.checks, "DQ-V05", "fail", "action outlier z>8")
                else:
                    _check(self.checks, "DQ-V05", "pass")
            else:
                _check(self.checks, "DQ-V05", "skip", "constant action")
        else:
            _check(self.checks, "DQ-V03", "fail", "no state/action values")
            _check(self.checks, "DQ-V05", "skip", "no action values")
        _check(self.checks, "DQ-V04", "skip", "no velocity feature in v1")
        _check(self.checks, "DQ-I09", "skip", "native images; no video")

    def _ensure_checks(self) -> None:
        present = {check.id for check in self.checks}
        for check_id in (
            "DQ-M01", "DQ-M02", "DQ-M03", "DQ-M04", "DQ-M05", "DQ-M06",
            "DQ-M07", "DQ-M08",
            "DQ-T01", "DQ-T02", "DQ-T03", "DQ-T04", "DQ-T05", "DQ-T06",
            "DQ-T07", "DQ-T08",
            "DQ-J01", "DQ-J02", "DQ-J03", "DQ-J04", "DQ-J05", "DQ-J06",
            "DQ-J07", "DQ-J08", "DQ-J09",
            "DQ-V01", "DQ-V02", "DQ-V03", "DQ-V04", "DQ-V05", "DQ-V06",
            "DQ-I01", "DQ-I02", "DQ-I03", "DQ-I04", "DQ-I05", "DQ-I06",
            "DQ-I07", "DQ-I08", "DQ-I09",
            "DQ-P01", "DQ-P02", "DQ-P03", "DQ-P04", "DQ-P05", "DQ-P06",
            "DQ-P07",
            "DQ-X01", "DQ-X02", "DQ-X03", "DQ-X04", "DQ-X05", "DQ-X06",
        ):
            if check_id not in present:
                _check(self.checks, check_id, "pass")

    # ------------------------------------------------------------------- run
    def run(self) -> Report:
        started = monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        if self._load():
            for entry in self.manifest.get("episodes", []):
                if isinstance(entry, dict):
                    self._check_episode(entry)
            self._check_provenance()
            self._check_cross()
            self._check_features()
        self._ensure_checks()
        self.checks = _aggregate_checks(self.checks)

        errors = sum(1 for c in self.checks if c.status == "fail" and c.severity == "error")
        warnings = sum(1 for c in self.checks if c.status == "fail" and c.severity == "warning")
        inconclusive = sum(1 for c in self.checks if c.status == "inconclusive")
        skipped = sum(1 for c in self.checks if c.status == "skip")
        if errors:
            result = "fail"
        elif inconclusive:
            result = "inconclusive"
        elif warnings:
            result = "degraded"
        else:
            result = "pass"

        software = self.provenance.get("software", {}) if self.provenance else {}
        dataset_id = str(self.manifest.get("dataset_id", ""))
        digest = ""
        if (self.root / "SHA256SUMS").is_file():
            digest = "sha256:" + root_hash(self.root)
        return Report(
            dataset={
                "id": dataset_id,
                "root_sha256": digest,
                "source_class": self.manifest.get("source_class"),
                "profile_id": _get(self.manifest, "robot", "adapter_id"),
                "profile_sha256": _get(self.manifest, "robot", "adapter_sha256"),
            },
            tool={
                "name": "jcheng-dataset",
                "version": __version__,
                "git_commit": software.get("git_commit", "unknown"),
                "lock_sha256": software.get("lock_sha256"),
            },
            run={
                "started_at": started_at,
                "duration_s": round(monotonic() - started, 3),
                "deterministic": True,
            },
            summary={
                "result": result,
                "usable_for_training": result == "pass",
                "errors": errors,
                "warnings": warnings,
                "skipped": skipped,
                "inconclusive": inconclusive,
                "checks": len(self.checks),
            },
            checks=self.checks,
            features={
                "observation.state": _stats(self.feature_values["observation.state"]),
                "action": _stats(self.feature_values["action"]),
            },
            episodes=self.episodes,
            limitations=self.limitations,
        )


def validate_dataset(root: Path) -> Report:
    return Validator(Path(root)).run()
