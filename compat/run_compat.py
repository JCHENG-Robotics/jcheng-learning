#!/usr/bin/env python3
"""Operator-run LeRobot v3 compatibility check (not packaged, not in CI)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="armpi_ultra")
    parser.add_argument("--native", default=None)
    parser.add_argument("--workdir", default="/tmp/jcheng-compat")
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()

    from jcheng_learning.lerobot.export import export_native_dataset
    from jcheng_learning.native import NativeDatasetReader
    from jcheng_learning.synthetic import generate
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    workdir = Path(args.workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    if args.native:
        native = Path(args.native)
    else:
        native, _ = generate(
            root=workdir / "native",
            profile_id=args.profile,
            episodes=2,
            frames=4,
            fps=10,
            seed=20261126,
            image_size=(16, 12),
            created_at="2026-11-26T00:00:00+08:00",
        )

    include_images = not args.no_images
    result = export_native_dataset(
        native, workdir / "export", mode="images", include_images=include_images
    )
    ds = LeRobotDataset("local/" + result.dataset_id, root=workdir / "export")
    reader = NativeDatasetReader(native)
    episodes = list(reader.episodes())
    frames = [frame for episode in episodes for frame in episode.frames]
    if len(ds) != len(frames):
        print(json.dumps({"result": "fail", "reason": "length mismatch"}))
        return 1
    max_state = max_action = 0.0
    max_image = 0
    index = 0
    for episode in episodes:
        for frame_index, frame in enumerate(episode.frames):
            state = ds[index]["observation.state"].numpy()
            action = ds[index]["action"].numpy()
            max_state = max(
                max_state,
                float(
                    np.max(
                        np.abs(
                            state
                            - np.asarray(frame["observation"]["state"], dtype=np.float32)
                        )
                    )
                ),
            )
            max_action = max(
                max_action,
                float(
                    np.max(
                        np.abs(
                            action
                            - np.asarray(frame["action"]["values"], dtype=np.float32)
                        )
                    )
                ),
            )
            if include_images:
                for camera in reader.manifest.get("cameras", []):
                    key = str(camera["key"])
                    image = ds[index][f"observation.images.{key}"].numpy()
                    image8 = np.rint(image.transpose(1, 2, 0) * 255).astype(np.uint8)
                    max_image = max(
                        max_image,
                        int(
                            np.max(
                                np.abs(
                                    image8.astype(int)
                                    - episode.image(frame_index, key).astype(int)
                                )
                            )
                        ),
                    )
            index += 1
    payload = {
        "schema": "jcheng.m1.compat-evidence.v1",
        "dataset_id": result.dataset_id,
        "lerobot_version": result.lerobot_version,
        "episodes": result.episodes,
        "frames": result.frames,
        "state_max_abs_diff": max_state,
        "action_max_abs_diff": max_action,
        "image_max_abs_diff": max_image if include_images else None,
        "result": "pass"
        if max_state == 0.0 and max_action == 0.0 and max_image == 0
        else "fail",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
