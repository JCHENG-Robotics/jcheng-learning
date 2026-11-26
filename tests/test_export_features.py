from pathlib import Path

import pytest

from jcheng_learning.errors import DependencyError
from jcheng_learning.lerobot.export import export_native_dataset
from jcheng_learning.lerobot.features import feature_map
from jcheng_learning.profiles import load_profile
from jcheng_learning.synthetic import generate


def test_feature_map_images():
    profile = load_profile("probe_2d")
    features = feature_map(
        profile,
        cameras=[{"key": "cam", "width": 8, "height": 8}],
        include_images=True,
        mode="images",
    )
    assert features["observation.state"]["shape"] == (2,)
    assert features["observation.state"]["names"] == ["j1", "j2"]
    assert features["observation.images.cam"] == {
        "dtype": "image",
        "shape": (8, 8, 3),
        "names": ["height", "width", "channels"],
    }


def test_feature_map_without_images():
    profile = load_profile("probe_2d")
    features = feature_map(
        profile, cameras=[], include_images=False, mode="images"
    )
    assert set(features) == {"observation.state", "action"}


def test_export_without_lerobot_is_a_dependency_error(tmp_path):
    root, _ = generate(
        root=tmp_path,
        profile_id="probe_2d",
        episodes=1,
        frames=2,
        fps=5,
        seed=1,
        image_size=(8, 8),
    )
    with pytest.raises(DependencyError, match="lerobot"):
        export_native_dataset(root, tmp_path / "export", include_images=False)
