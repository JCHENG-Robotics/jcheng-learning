from pathlib import Path

import pytest

from jcheng_learning.errors import DatasetError
from jcheng_learning.lerobot import import_lerobot_v3
from jcheng_learning.native import NativeDatasetReader
from jcheng_learning.validate import validate_dataset

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lerobot_v3_min"


def test_import_fixture_to_native(tmp_path):
    root, digest = import_lerobot_v3(
        source=FIXTURE,
        profile_id="probe_2d",
        source_class="simulation",
        out=tmp_path,
        repo_id="fixture/min",
        revision="local",
        license="internal",
        public=False,
        include_images=True,
        created_at="2026-01-01T00:00:00+08:00",
    )
    assert root.name == "public-probe_2d-local"
    reader = NativeDatasetReader(root)
    assert reader.root_hash == digest
    episodes = list(reader.episodes())
    assert len(episodes) == 2
    first = episodes[0].frames[0]
    assert first["observation"]["state"] == [0.0, 0.0]
    assert first["action"]["values"] == [0.5, 0.5]
    assert first["observation"]["truth"] == "unknown"
    assert episodes[0].image(0, "cam").shape == (8, 8, 3)

    report = validate_dataset(root)
    payload = report.to_dict()
    assert payload["summary"]["result"] == "pass", [
        (c["id"], c["status"], c["message"]) for c in payload["checks"] if c["status"] != "pass"
    ]


def test_import_without_images(tmp_path):
    root, _ = import_lerobot_v3(
        source=FIXTURE,
        profile_id="probe_2d",
        source_class="simulation",
        out=tmp_path,
        license="internal",
        include_images=False,
        created_at="2026-01-01T00:00:00+08:00",
    )
    reader = NativeDatasetReader(root)
    assert reader.manifest["cameras"] == []
    report = validate_dataset(root)
    assert report.to_dict()["summary"]["result"] == "pass"


def test_import_rejects_name_mismatch(tmp_path):
    with pytest.raises(DatasetError, match="state names differ"):
        import_lerobot_v3(
            source=FIXTURE,
            profile_id="armpi_ultra",
            source_class="simulation",
            out=tmp_path,
            license="internal",
            include_images=False,
        )


def test_public_real_requires_license(tmp_path):
    with pytest.raises(DatasetError, match="requires --license"):
        import_lerobot_v3(
            source=FIXTURE,
            profile_id="probe_2d",
            source_class="public-real",
            out=tmp_path,
            include_images=False,
        )
