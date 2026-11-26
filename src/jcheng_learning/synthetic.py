"""Deterministic synthetic episodes for offline tests.

No device, no network, no ROS. The generator uses a small integer LCG so the
values do not depend on CPython's ``random`` implementation. Byte-level
determinism still requires the same interpreter, locked dependencies, seed and
``created_at``.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .errors import DatasetError
from .native.writer import NativeDatasetWriter
from .profiles import Profile, load_profile
from .provenance import software_block
from .version import __version__


class _LCG:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def u32(self) -> int:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * (self.u32() / 2**32)


def _config_hash(
    profile: Profile,
    episodes: int,
    frames: int,
    fps: int,
    seed: int,
    image_size: tuple[int, int] | None,
    created_at: str,
) -> str:
    payload = {
        "profile": profile.id,
        "profile_version": profile.version,
        "episodes": episodes,
        "frames": frames,
        "fps": fps,
        "seed": seed,
        "image_size": list(image_size) if image_size else None,
        "created_at": created_at,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _joint_value(joint, frame: int, fps: int, rng: _LCG) -> float:
    unit_scale = 1.0 if joint.unit in {"rad", "m"} else 180.0
    if joint.lower is not None and joint.upper is not None:
        base = 0.5 * (joint.lower + joint.upper)
        amplitude = 0.2 * (joint.upper - joint.lower)
    else:
        base = 0.0
        amplitude = 0.2 * unit_scale
    phase = 0.7 * joint.index
    period = 1.3 + 0.2 * joint.index
    noise = rng.uniform(-0.01, 0.01) * unit_scale
    return base + amplitude * math.sin(2 * math.pi * (frame / (fps * period) + phase)) + noise


def _gripper_value(profile: Profile, frame: int, frames: int, rng: _LCG) -> float:
    gripper = profile.gripper
    if gripper is None:
        return 0.0
    opened = frame < frames // 2
    if gripper.space in {"canonical", "linear"}:
        return float(gripper.open if opened else gripper.closed)
    if gripper.space == "normalized":
        return 1.0 if opened else 0.0
    if gripper.space == "raw_joint":
        raw = gripper.raw_space or {}
        return float(raw.get("upper", 0.0) if opened else raw.get("lower", 0.0))
    return 0.0


def _image(width: int, height: int, frame: int, seed: int, camera_index: int) -> np.ndarray:
    ys, xs = np.mgrid[0:height, 0:width]
    red = (xs * 3 + seed * 7 + frame * 5 + camera_index * 13) % 256
    green = (ys * 5 + seed * 11 + camera_index * 29) % 256
    blue = (xs + ys + frame * 3 + camera_index * 41) % 256
    image = np.stack([red, green, blue], axis=-1).astype(np.uint8)
    square = 8 if min(width, height) >= 16 else 4
    x0 = (frame * 2) % max(1, width - square)
    y0 = frame % max(1, height - square)
    image[y0 : y0 + square, x0 : x0 + square, :] = 255
    return image


def generate(
    *,
    root: Path,
    profile_id: str,
    episodes: int = 3,
    frames: int = 40,
    fps: int = 10,
    seed: int = 0,
    created_at: str = "2026-01-01T00:00:00+08:00",
    image_size: tuple[int, int] | None = (64, 48),
) -> tuple[Path, str]:
    if episodes < 1 or frames < 2:
        raise DatasetError("episodes must be >= 1 and frames >= 2")
    profile = load_profile(profile_id)
    if image_size is None and profile.cameras:
        image_size = (profile.cameras[0].width, profile.cameras[0].height)
    if image_size is not None and image_size[0] < 8 or image_size is not None and image_size[1] < 8:
        raise DatasetError("image size must be at least 8x8")

    dataset_id = f"synthetic-{profile_id}-{seed:08x}"
    start_ns = 1_000_000_000
    rng = _LCG(seed)
    software = software_block()

    origin = {
        "kind": "generator",
        "public": False,
        "generator": {
            "name": "jcheng-dataset",
            "version": __version__,
            "seed": seed,
            "config_sha256": _config_hash(
                profile, episodes, frames, fps, seed, image_size, created_at
            ),
        },
    }
    calibration = [
        {
            "id": f"synthetic-{camera.key}",
            "kind": "synthetic",
            "sha256": "sha256:"
            + hashlib.sha256(f"{profile.id}/{camera.key}".encode("utf-8")).hexdigest(),
        }
        for camera in profile.cameras
    ]

    writer = NativeDatasetWriter(
        root,
        dataset_id,
        "synthetic",
        profile,
        fps=fps,
        created_at=created_at,
        state_truth="measured",
        truth_source="generator_truth",
        capture={
            "method": "generator",
            "operator_session_id": None,
            "authorization_ref": None,
            "started_at": created_at,
            "ended_at": created_at,
        },
        calibration=calibration,
        license_block={"dataset": "internal", "consent": None, "redistribution": "none"},
        origin=origin,
        software=software,
        image_size=image_size,
    )

    state_dim = len(profile.state_space().names)
    action_dim = len(profile.action_space().names)
    for episode_index in range(episodes):
        episode_id = f"ep_{episode_index:04d}"
        writer.begin_episode(
            episode_id,
            "pick the cube",
            outcome="success" if episode_index % 2 == 0 else "failure",
            start_ns=start_ns,
        )
        previous = None
        for frame in range(frames):
            t_ns = start_ns + round(frame * 1e9 / fps)
            values = [
                _joint_value(joint, frame, fps, rng) for joint in profile.joints
            ]
            if profile.gripper is not None:
                values.append(_gripper_value(profile, frame, frames, rng))
            if len(values) != state_dim:
                raise DatasetError("synthetic state dimension does not match profile")
            if previous is None:
                action = list(values)
            else:
                action = list(values)
                gripper_index = (
                    profile.gripper.index if profile.gripper is not None else None
                )
                for index, value in enumerate(values):
                    if index == gripper_index:
                        continue
                    candidate = value + 0.02 * math.sin(frame + index)
                    if index < len(profile.joints):
                        joint = profile.joints[index]
                        if joint.lower is not None and joint.upper is not None:
                            candidate = min(max(candidate, joint.lower), joint.upper)
                    action[index] = candidate
            if len(action) != action_dim:
                raise DatasetError("synthetic action dimension does not match profile")
            images = {}
            for camera_index, camera in enumerate(profile.cameras):
                if image_size is None:
                    raise DatasetError("camera profile requires an image size")
                pixels = _image(
                    image_size[0], image_size[1], frame, seed + episode_index * 17, camera_index
                )
                images[camera.key] = (pixels, t_ns)
            writer.add_frame(
                t_ns=t_ns,
                state=values,
                action=action,
                images=images,
                truth="measured",
            )
            previous = values
        writer.end_episode()

    digest = writer.finalize()
    return writer.root, digest
