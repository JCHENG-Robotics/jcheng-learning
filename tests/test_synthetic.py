import yaml

from jcheng_learning.synthetic import generate


def _manifest(root):
    return yaml.safe_load((root / "dataset.yaml").read_text(encoding="utf-8"))


def test_synthetic_is_deterministic(tmp_path):
    first_root, first_hash = generate(
        root=tmp_path / "a",
        profile_id="armpi_ultra",
        episodes=2,
        frames=6,
        fps=10,
        seed=7,
        created_at="2026-01-01T00:00:00+08:00",
        image_size=(32, 24),
    )
    second_root, second_hash = generate(
        root=tmp_path / "b",
        profile_id="armpi_ultra",
        episodes=2,
        frames=6,
        fps=10,
        seed=7,
        created_at="2026-01-01T00:00:00+08:00",
        image_size=(32, 24),
    )
    assert first_hash == second_hash
    assert (first_root / "SHA256SUMS").read_bytes() == (
        second_root / "SHA256SUMS"
    ).read_bytes()


def test_synthetic_manifest(tmp_path):
    root, digest = generate(
        root=tmp_path,
        profile_id="armpi_ultra",
        episodes=2,
        frames=6,
        fps=10,
        seed=0,
        image_size=(32, 24),
    )
    manifest = _manifest(root)
    assert manifest["schema"] == "jcheng.dataset.v1"
    assert manifest["source_class"] == "synthetic"
    assert manifest["state"]["truth"] == "measured"
    assert manifest["state"]["truth_source"] == "generator_truth"
    assert manifest["action"]["space_id"] == "armpi_ultra.joint_position_absolute.v1"
    assert manifest["timing"]["nominal_fps"] == 10
    assert len(manifest["episodes"]) == 2
    assert [episode["frames"] for episode in manifest["episodes"]] == [6, 6]
    assert {camera["key"] for camera in manifest["cameras"]} == {"external", "wrist"}
    assert {camera["width"] for camera in manifest["cameras"]} == {32}
    assert digest.startswith("sha256:") or len(digest) == 64


def test_gate2_synthetic_has_no_cameras(tmp_path):
    root, _ = generate(
        root=tmp_path,
        profile_id="gate2_arm",
        episodes=1,
        frames=4,
        fps=5,
        seed=1,
        image_size=None,
    )
    manifest = _manifest(root)
    assert manifest["cameras"] == []
    assert manifest["state"]["names"] == ["joint1", "joint2"]
    assert manifest["action"]["names"] == ["joint1", "joint2"]
