import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from jcheng_learning.io.hashing import write_sha256sums
from jcheng_learning.synthetic import generate
from jcheng_learning.validate import validate_dataset

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "src/jcheng_learning/schemas/jcheng.dataset-quality-report.v1.schema.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture()
def dataset(tmp_path):
    root, _ = generate(
        root=tmp_path,
        profile_id="armpi_ultra",
        episodes=1,
        frames=4,
        fps=10,
        seed=2,
        image_size=(16, 12),
    )
    return root


def _resign(root: Path) -> None:
    write_sha256sums(root)


def _manifest(root: Path) -> dict:
    return yaml.safe_load((root / "dataset.yaml").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict) -> None:
    (root / "dataset.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    _resign(root)


def _frames(root: Path) -> tuple[Path, list[dict]]:
    path = root / "episodes" / "ep_0000" / "frames.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return path, rows


def _write_frames(path: Path, rows: list[dict], root: Path) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    _resign(root)


def _provenance(root: Path) -> dict:
    return json.loads((root / "provenance.json").read_text(encoding="utf-8"))


def _write_provenance(root: Path, data: dict) -> None:
    (root / "provenance.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _resign(root)


def _set_source(root: Path, source_class: str, *, truth_source: str | None = None,
                auth: bool = True, calibration: bool = True) -> None:
    manifest = _manifest(root)
    manifest["source_class"] = source_class
    if truth_source is not None:
        manifest["state"]["truth_source"] = truth_source
    if source_class == "public-real":
        manifest["state"]["truth"] = "unknown"
    _write_manifest(root, manifest)
    provenance = _provenance(root)
    provenance["source_class"] = source_class
    provenance["capture"] = {
        "method": "generator",
        "operator_session_id": "session" if auth else None,
        "authorization_ref": "auth" if auth else None,
        "started_at": "2026-01-01T00:00:00+08:00",
        "ended_at": "2026-01-01T00:00:01+08:00",
    }
    provenance["calibration"] = (
        [{"id": "calib", "kind": "synthetic", "sha256": "sha256:" + "0" * 64}]
        if calibration
        else []
    )
    provenance["license"] = {"dataset": "proprietary", "consent": None, "redistribution": "none"}
    if source_class == "simulation":
        provenance["origin"] = {
            "kind": "simulator",
            "public": False,
            "simulator": {"repo": "jcheng-simulation", "profile_hash": "sha256:" + "0" * 64},
        }
    _write_provenance(root, provenance)


def _has_fail(report, check_id: str) -> bool:
    return any(check.id == check_id and check.status == "fail" for check in report.checks)


def test_positive_dataset_passes_and_schema(dataset):
    report = validate_dataset(dataset)
    payload = report.to_dict()
    assert payload["summary"]["result"] == "pass"
    assert payload["summary"]["errors"] == 0
    assert payload["summary"]["usable_for_training"] is True
    jsonschema.validate(payload, SCHEMA)
    ids = {check["id"] for check in payload["checks"]}
    assert "DQ-M04" in ids
    assert "DQ-J02" in ids
    assert "DQ-I04" in ids


def test_nan_state(dataset):
    path, rows = _frames(dataset)
    rows[0]["observation"]["state"][0] = float("nan")
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-V01")


def test_missing_camera_entry(dataset):
    path, rows = _frames(dataset)
    del rows[0]["observation"]["images"]["external"]
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-I01")


def test_wrong_state_dimension(dataset):
    path, rows = _frames(dataset)
    rows[0]["observation"]["state"].pop()
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-J01")


def test_joint_order_permutation(dataset):
    manifest = _manifest(dataset)
    names = manifest["state"]["names"]
    names[1], names[2] = names[2], names[1]
    _write_manifest(dataset, manifest)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-J02")


def test_corrupt_image(dataset):
    image = dataset / "episodes" / "ep_0000" / "images" / "external" / "000000.png"
    image.write_bytes(b"not a png")
    _resign(dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-I03")


def test_image_shape_mismatch(dataset):
    from PIL import Image
    import numpy as np

    image = dataset / "episodes" / "ep_0000" / "images" / "external" / "000000.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(image, format="PNG")
    _resign(dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-I04")


def test_timestamp_regression(dataset):
    path, rows = _frames(dataset)
    rows[1]["t_ns"] = rows[0]["t_ns"] - 1
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-T02")


def test_duplicate_timestamp(dataset):
    path, rows = _frames(dataset)
    rows[1]["t_ns"] = rows[0]["t_ns"]
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-T05")


def test_hash_mismatch_is_detected(dataset):
    path, rows = _frames(dataset)
    rows[0]["observation"]["state"][0] += 1.0
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-M04")


def test_own_real_requires_si(dataset):
    _set_source(dataset, "own-real", truth_source="bus_read")
    manifest = _manifest(dataset)
    manifest["state"]["units"][0] = "deg"
    _write_manifest(dataset, manifest)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-J04")


def test_gripper_space_mismatch(dataset):
    manifest = _manifest(dataset)
    manifest["action"]["gripper"]["space"] = "raw_joint"
    _write_manifest(dataset, manifest)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-J06")


def test_own_real_requires_authorization(dataset):
    _set_source(dataset, "own-real", truth_source="command_cache", auth=False)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-P05")


def test_bus_read_requires_measurements(dataset):
    _set_source(dataset, "own-real", truth_source="bus_read")
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-P02")


def test_truth_source_must_match_source_class(dataset):
    _set_source(dataset, "simulation", truth_source="generator_truth")
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-P07")


def test_task_must_be_declared(dataset):
    manifest = _manifest(dataset)
    manifest["tasks"] = []
    _write_manifest(dataset, manifest)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-X05")


def test_action_jump(dataset):
    path, rows = _frames(dataset)
    rows[1]["action"]["values"][0] = 100.0
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-V06")


def test_missing_file_without_resigning(dataset):
    image = dataset / "episodes" / "ep_0000" / "images" / "external" / "000000.png"
    image.unlink()
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-M04")


def test_inf_action(dataset):
    path, rows = _frames(dataset)
    rows[0]["action"]["values"][0] = float("inf")
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-V01")


def test_wrong_action_dimension(dataset):
    path, rows = _frames(dataset)
    rows[0]["action"]["values"].append(0.0)
    _write_frames(path, rows, dataset)
    report = validate_dataset(dataset)
    assert _has_fail(report, "DQ-J01")
