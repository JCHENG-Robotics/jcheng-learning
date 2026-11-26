"""Map native features to LeRobot Dataset v3 features."""

from __future__ import annotations

from typing import Any

from ..errors import DatasetError
from ..profiles import Profile


def feature_map(
    profile: Profile,
    *,
    cameras: list[dict[str, Any]],
    include_images: bool,
    mode: str,
) -> dict[str, dict[str, Any]]:
    if mode not in {"images", "videos"}:
        raise DatasetError(f"unsupported export mode {mode!r}")
    features: dict[str, dict[str, Any]] = {
        "observation.state": {
            "dtype": "float32",
            "shape": (len(profile.state_space().names),),
            "names": list(profile.state_space().names),
        },
        "action": {
            "dtype": "float32",
            "shape": (len(profile.action_space().names),),
            "names": list(profile.action_space().names),
        },
    }
    if not include_images:
        return features
    if not cameras:
        raise DatasetError("include_images is true but the dataset declares no cameras")
    for camera in cameras:
        key = str(camera["key"])
        features[f"observation.images.{key}"] = {
            "dtype": "image" if mode == "images" else "video",
            "shape": (int(camera["height"]), int(camera["width"]), 3),
            "names": ["height", "width", "channels"],
        }
    return features


def feature_rename_map(features: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Identity map for readability in the export sidecar."""

    return {name: name for name in features}
