from pathlib import Path

import pytest

from jcheng_learning.errors import DatasetError
from jcheng_learning.evaluate import _rename_cameras
from jcheng_learning.train import train_rehearsal


def test_train_and_eval_modules_import_without_torch():
    import jcheng_learning.evaluate  # noqa: F401
    import jcheng_learning.train  # noqa: F401


def test_rename_cameras():
    sample = {
        "observation.images.external": 1,
        "observation.images.wrist": 2,
        "observation.state": 3,
    }
    renamed = _rename_cameras(sample, 2)
    assert renamed["observation.images.camera1"] == 1
    assert renamed["observation.images.camera2"] == 2
    assert "observation.images.external" not in renamed


def test_train_rehearsal_rejects_missing_dataset(tmp_path):
    with pytest.raises(DatasetError):
        train_rehearsal(
            train_root=tmp_path / "missing",
            out=tmp_path / "run",
            steps=1,
            batch_size=1,
        )
