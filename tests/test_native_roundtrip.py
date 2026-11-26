import json

import numpy as np
import pytest

from jcheng_learning.errors import DatasetError
from jcheng_learning.native import NativeDatasetReader
from jcheng_learning.synthetic import _image, generate


@pytest.fixture()
def dataset(tmp_path):
    root, digest = generate(
        root=tmp_path,
        profile_id="armpi_ultra",
        episodes=2,
        frames=6,
        fps=10,
        seed=3,
        image_size=(32, 24),
    )
    return root, digest


def test_native_roundtrip(dataset):
    root, digest = dataset
    reader = NativeDatasetReader(root)
    episodes = list(reader.episodes())
    assert len(episodes) == 2
    assert reader.dataset_id.startswith("synthetic-armpi_ultra-")
    assert reader.root_hash == digest
    first = episodes[0]
    assert len(first.frames) == 6
    frame = first.frames[0]
    assert len(frame["observation"]["state"]) == 6
    assert len(frame["action"]["values"]) == 6
    assert frame["observation"]["truth"] == "measured"

    expected = _image(32, 24, 0, 3, 0)
    actual = first.image(0, "external")
    assert np.array_equal(actual, expected)
    assert actual.dtype == np.uint8


def test_tampered_file_is_rejected(dataset):
    root, _ = dataset
    frames_path = root / "episodes" / "ep_0000" / "frames.jsonl"
    lines = frames_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["observation"]["state"][0] += 1.0
    lines[0] = json.dumps(row, sort_keys=True)
    frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="integrity failure"):
        NativeDatasetReader(root)


def test_missing_image_is_rejected(dataset):
    root, _ = dataset
    (root / "episodes" / "ep_0000" / "images" / "external" / "000000.png").unlink()
    with pytest.raises(DatasetError, match="integrity failure"):
        NativeDatasetReader(root)
