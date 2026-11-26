"""Import a public LeRobot v3 dataset into the JCHENG native store.

Numbers are preserved bit-for-bit as float32 values (read through Python
floats). Units are preserved from the source and declared; they are never
silently converted to SI. A public dataset therefore keeps
``si_conformant: false`` when its source uses degrees or pixels.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..errors import DatasetError, DependencyError
from ..io.hashing import file_sha256
from ..native.writer import NativeDatasetWriter
from ..profiles import Profile, load_profile
from ..provenance import now_iso, software_block
from .v3_reader import LeRobotV3Reader

SOURCE_CLASSES = {"public-real", "simulation"}


def _decode_image(payload: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            return np.asarray(image.convert("RGB"), dtype=np.uint8)
    except (OSError, ValueError) as exc:
        raise DatasetError(f"cannot decode embedded image: {exc}") from exc


def _files_digest(root: Path) -> tuple[list[dict[str, str]], str]:
    files = []
    import hashlib

    aggregate = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = file_sha256(path)
        files.append({"path": rel, "sha256": "sha256:" + digest})
        aggregate.update(rel.encode("utf-8"))
        aggregate.update(bytes.fromhex(digest))
    return files, "sha256:" + aggregate.hexdigest()


def import_lerobot_v3(
    *,
    source: Path,
    profile_id: str,
    source_class: str,
    out: Path,
    repo_id: str | None = None,
    revision: str | None = None,
    license: str | None = None,
    public: bool = False,
    include_images: bool = True,
    created_at: str | None = None,
    dataset_id: str | None = None,
) -> tuple[Path, str]:
    if source_class not in SOURCE_CLASSES:
        raise DatasetError("source_class must be public-real or simulation")
    if source_class == "public-real" and not license:
        raise DatasetError("public-real import requires --license")
    reader = LeRobotV3Reader(source)
    profile: Profile = load_profile(profile_id)

    if not reader.state_names:
        raise DatasetError("source dataset has no observation.state names")
    if reader.state_names != profile.state_space().names:
        raise DatasetError(
            f"state names differ: source={reader.state_names} profile={profile.state_space().names}"
        )
    if reader.action_names != profile.action_space().names:
        raise DatasetError(
            f"action names differ: source={reader.action_names} profile={profile.action_space().names}"
        )
    if include_images and reader.video_keys:
        raise DependencyError(
            "video decoding is not implemented in S3; re-run with --no-images"
        )
    if include_images and not reader.image_keys and profile.cameras:
        raise DatasetError("source has no image features; re-run with --no-images")

    created = created_at or now_iso()
    repo = repo_id or "local"
    rev = revision or "local"
    safe_rev = re.sub(r"[^a-z0-9._-]", "-", rev.lower())[:12]
    dataset_id = dataset_id or f"public-{profile.id}-{safe_rev}"
    files, files_digest = _files_digest(source)
    upstream = {
        "repo_id": repo,
        "revision": rev,
        "license": license or "internal",
        "files": files,
        "files_sha256": files_digest,
    }
    origin: dict[str, Any] = {
        "kind": "public-dataset",
        "public": bool(public),
    }
    if source_class == "simulation":
        origin["simulator"] = {"repo": repo, "version": rev}

    writer = NativeDatasetWriter(
        out,
        dataset_id,
        source_class,
        profile,
        fps=reader.fps,
        created_at=created,
        state_truth="unknown",
        truth_source="source_dataset",
        capture={
            "method": "import",
            "operator_session_id": None,
            "authorization_ref": None,
            "started_at": created,
            "ended_at": created,
        },
        calibration=[],
        license_block={
            "dataset": license or "internal",
            "consent": None,
            "redistribution": "none",
        },
        origin=origin,
        software=software_block(),
        upstream=upstream,
        transformations=[
            {
                "tool": "jcheng-dataset",
                "version": software_block()["jcheng_learning"],
                "at": created,
                "operation": "import-lerobot-v3",
                "input": {"repo_id": repo, "revision": rev, "files_sha256": files_digest},
                "params": {"profile": profile.id, "include_images": bool(include_images)},
            }
        ],
        include_images=include_images,
    )

    start_ns = 1_000_000_000
    for episode in reader.episodes():
        task = episode.tasks[0] if episode.tasks and episode.tasks[0] else "imported episode"
        writer.begin_episode(
            f"ep_{episode.episode_index:04d}",
            task,
            outcome="unknown",
            start_ns=start_ns,
        )
        first_timestamp = episode.frames[0].timestamp
        for frame in episode.frames:
            t_ns = start_ns + round((frame.timestamp - first_timestamp) * 1e9)
            images: dict[str, tuple[np.ndarray, int]] = {}
            if include_images:
                for camera_key, payload in frame.images.items():
                    images[camera_key] = (_decode_image(payload), t_ns)
            writer.add_frame(
                t_ns=t_ns,
                state=list(frame.state),
                action=list(frame.action),
                images=images,
                truth="unknown",
            )
        writer.end_episode()
    digest = writer.finalize()
    return writer.root, digest
