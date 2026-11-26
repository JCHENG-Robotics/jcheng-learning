import json
import shutil
from pathlib import Path

import pytest

from jcheng_learning.errors import InconclusiveError
from jcheng_learning.lerobot import LeRobotV3Reader

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lerobot_v3_min"


def test_fixture_metadata():
    reader = LeRobotV3Reader(FIXTURE)
    assert reader.fps == 5
    assert reader.total_episodes == 2
    assert reader.total_frames == 8
    assert reader.state_names == ("j1", "j2")
    assert reader.action_names == ("j1", "j2")
    assert reader.image_keys == ["observation.images.cam"]
    assert reader.video_keys == []
    assert reader.tasks() == {0: "probe task"}


def test_fixture_episodes_and_images():
    reader = LeRobotV3Reader(FIXTURE)
    episodes = list(reader.episodes())
    assert [episode.length for episode in episodes] == [4, 4]
    first = episodes[0].frames[0]
    assert first.state == (0.0, 0.0)
    assert first.action == (0.5, 0.5)
    assert "cam" in first.images
    assert first.images["cam"].startswith(b"\x89PNG")


def test_version_gate(tmp_path):
    target = tmp_path / "v2"
    shutil.copytree(FIXTURE, target)
    info = json.loads((target / "meta/info.json").read_text())
    info["codebase_version"] = "v2.1"
    (target / "meta/info.json").write_text(json.dumps(info))
    with pytest.raises(InconclusiveError):
        LeRobotV3Reader(target)
