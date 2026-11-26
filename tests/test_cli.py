import json
from pathlib import Path

from jcheng_learning.cli import main


def test_cli_synth_inspect_hash(tmp_path, capsys):
    out = tmp_path / "out"
    assert main([
        "synth",
        "--profile", "armpi_ultra",
        "--out", str(out),
        "--episodes", "1",
        "--frames", "4",
        "--seed", "5",
        "--created-at", "2026-01-01T00:00:00+08:00",
        "--image-size", "16x12",
    ]) == 0
    captured = capsys.readouterr().out
    assert "root_sha256:" in captured
    dataset = out / "synthetic-armpi_ultra-00000005"
    assert dataset.is_dir()

    assert main(["hash", str(dataset)]) == 0
    digest = capsys.readouterr().out.strip()
    assert len(digest) == 64

    assert main(["inspect", str(dataset)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["dataset_id"] == "synthetic-armpi_ultra-00000005"
    assert summary["episodes"] == 1
    assert summary["frames"] == 4


def test_cli_profile_list_and_show(capsys):
    assert main(["profile", "list"]) == 0
    assert "armpi_ultra" in capsys.readouterr().out
    assert main(["profile", "show", "piper_x"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["dof"] == 6
    assert shown["action_spaces"] == ["piper_x.joint_position_absolute.v1"]


def test_cli_unknown_profile_returns_dataset_error(tmp_path):
    assert main([
        "synth",
        "--profile", "does_not_exist",
        "--out", str(tmp_path),
    ]) == 1


def test_cli_profile_show_without_id_returns_usage_error():
    assert main(["profile", "show"]) == 2


def test_cli_validate_report_and_stats(tmp_path, capsys):
    out = tmp_path / "out"
    assert main([
        "synth", "--profile", "armpi_ultra", "--out", str(out),
        "--episodes", "1", "--frames", "4", "--seed", "6",
        "--image-size", "16x12",
    ]) == 0
    dataset = out / "synthetic-armpi_ultra-00000006"
    report_path = tmp_path / "quality.json"
    assert main(["validate", str(dataset), "--report", str(report_path)]) == 0
    assert report_path.is_file()
    assert main(["report", str(report_path), "--format", "md"]) == 0
    assert "Dataset quality report" in capsys.readouterr().out
    assert main(["stats", str(dataset)]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["action"]["count"] == 24


def test_cli_validate_rejects_bad_dataset(tmp_path):
    out = tmp_path / "out"
    assert main([
        "synth", "--profile", "armpi_ultra", "--out", str(out),
        "--episodes", "1", "--frames", "4", "--seed", "7",
        "--image-size", "16x12",
    ]) == 0
    dataset = out / "synthetic-armpi_ultra-00000007"
    frames = dataset / "episodes" / "ep_0000" / "frames.jsonl"
    frames.write_text(frames.read_text().replace('"state": [', '"state": [1.0, ', 1))
    assert main(["validate", str(dataset)]) == 1


def test_cli_import_fixture(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures" / "lerobot_v3_min"
    out = tmp_path / "native"
    assert main([
        "import", str(fixture),
        "--profile", "probe_2d",
        "--source-class", "simulation",
        "--out", str(out),
        "--license", "internal",
        "--no-images",
        "--created-at", "2026-01-01T00:00:00+08:00",
    ]) == 0
    dataset = out / "public-probe_2d-local"
    assert dataset.is_dir()
    assert main(["validate", str(dataset)]) == 0
