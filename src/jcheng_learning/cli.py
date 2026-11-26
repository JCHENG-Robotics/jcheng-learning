"""Command-line entry point for offline dataset work.

M1/S1 exposes ``synth``, ``inspect``, ``hash`` and ``profile``. Validation,
import and export are added in S2–S4 behind the same error/exit-code contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import DatasetError, InconclusiveError, JchengError, UsageError
from .lerobot import import_lerobot_v3
from .lerobot.export import export_native_dataset
from .native.reader import NativeDatasetReader
from .profiles import list_profiles, load_profile
from .report import render_markdown
from .synthetic import generate
from .validate import validate_dataset
from .version import __version__


def _parse_size(text: str) -> tuple[int, int]:
    try:
        width, height = text.lower().split("x", 1)
        return int(width), int(height)
    except ValueError as exc:
        raise UsageError(f"invalid image size {text!r}; expected WxH") from exc


def _cmd_profile(args: argparse.Namespace) -> int:
    if args.action == "list":
        for profile_id in list_profiles():
            print(profile_id)
        return 0
    profile = load_profile(args.profile_id)
    print(
        json.dumps(
            {
                "id": profile.id,
                "version": profile.version,
                "dof": profile.dof,
                "has_gripper": profile.has_gripper,
                "state_spaces": [space.id for space in profile.state_spaces],
                "action_spaces": [space.id for space in profile.action_spaces],
                "cameras": [camera.key for camera in profile.cameras],
                "capabilities": profile.capabilities,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_synth(args: argparse.Namespace) -> int:
    image_size = _parse_size(args.image_size) if args.image_size else None
    root, digest = generate(
        root=Path(args.out),
        profile_id=args.profile,
        episodes=args.episodes,
        frames=args.frames,
        fps=args.fps,
        seed=args.seed,
        created_at=args.created_at,
        image_size=image_size,
    )
    print(f"dataset: {root}")
    print(f"root_sha256: {digest}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    reader = NativeDatasetReader(Path(args.dataset))
    manifest = reader.manifest
    episodes = list(reader.episodes())
    print(
        json.dumps(
            {
                "dataset_id": reader.dataset_id,
                "source_class": manifest.get("source_class"),
                "profile": manifest.get("robot", {}).get("adapter_id"),
                "episodes": len(episodes),
                "frames": sum(len(episode.frames) for episode in episodes),
                "tasks": manifest.get("tasks", []),
                "root_sha256": reader.root_hash,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    reader = NativeDatasetReader(Path(args.dataset))
    print(reader.root_hash)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.dataset)
    if args.profile:
        reader = NativeDatasetReader(root, verify=False)
        actual = str(reader.manifest.get("robot", {}).get("adapter_id"))
        if actual != args.profile:
            raise DatasetError(f"dataset profile is {actual!r}, not {args.profile!r}")
    report = validate_dataset(root)
    payload = report.to_dict()
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            f"result: {summary['result']}  errors={summary['errors']} "
            f"warnings={summary['warnings']} inconclusive={summary['inconclusive']} "
            f"skipped={summary['skipped']}"
        )
        for check in payload["checks"]:
            if check["status"] in {"fail", "inconclusive"}:
                print(f"{check['id']} {check['status']}: {check['message']}")
    result = payload["summary"]["result"]
    if result == "fail":
        raise DatasetError("dataset rejected")
    if result == "inconclusive":
        raise InconclusiveError("dataset validation is inconclusive")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    report = validate_dataset(Path(args.dataset))
    print(json.dumps(report.to_dict()["features"], indent=2, sort_keys=True))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"invalid report JSON: {exc}") from exc
    if payload.get("schema") != "jcheng.dataset-quality-report.v1":
        raise DatasetError("unsupported report schema")
    if args.format == "md":
        print(render_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    if args.format != "lerobot":
        raise UsageError("only --format lerobot is implemented in S3")
    root, digest = import_lerobot_v3(
        source=Path(args.source),
        profile_id=args.profile,
        source_class=args.source_class,
        out=Path(args.out),
        repo_id=args.repo_id,
        revision=args.revision,
        license=args.license,
        public=args.public,
        include_images=not args.no_images,
        created_at=args.created_at,
        dataset_id=args.dataset_id,
    )
    print(f"dataset: {root}")
    print(f"root_sha256: {digest}")
    return 0


def _cmd_convert(args: argparse.Namespace) -> int:
    if args.to != "lerobot":
        raise UsageError("only --to lerobot is implemented")
    reader = NativeDatasetReader(Path(args.dataset), verify=False)
    fps = int(reader.manifest["timing"]["nominal_fps"])
    if args.fps is not None and args.fps != fps:
        raise UsageError(f"--fps {args.fps} != dataset fps {fps}; resampling is not implemented")
    result = export_native_dataset(
        Path(args.dataset),
        Path(args.out),
        mode=args.mode,
        include_images=not args.no_images,
        sample_policy=args.sample_policy,
    )
    print(f"export: {result.root}")
    print(
        f"episodes={result.episodes} frames={result.frames} "
        f"dropped={result.dropped_frames} lerobot={result.lerobot_version}"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jcheng-dataset")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile = subparsers.add_parser("profile", help="list or show robot profiles")
    profile.add_argument("action", choices=["list", "show"])
    profile.add_argument("profile_id", nargs="?")
    profile.set_defaults(func=_cmd_profile)

    synth = subparsers.add_parser("synth", help="generate deterministic synthetic data")
    synth.add_argument("--profile", required=True)
    synth.add_argument("--out", required=True)
    synth.add_argument("--episodes", type=int, default=3)
    synth.add_argument("--frames", type=int, default=40)
    synth.add_argument("--fps", type=int, default=10)
    synth.add_argument("--seed", type=int, default=0)
    synth.add_argument("--created-at", default="2026-01-01T00:00:00+08:00")
    synth.add_argument("--image-size", default="64x48", help="WxH")
    synth.set_defaults(func=_cmd_synth)

    inspect = subparsers.add_parser("inspect", help="summarize a native dataset")
    inspect.add_argument("dataset")
    inspect.set_defaults(func=_cmd_inspect)

    hash_cmd = subparsers.add_parser("hash", help="print the dataset root hash")
    hash_cmd.add_argument("dataset")
    hash_cmd.set_defaults(func=_cmd_hash)

    validate = subparsers.add_parser("validate", help="validate a native dataset")
    validate.add_argument("dataset")
    validate.add_argument("--profile", default=None)
    validate.add_argument("--report", default=None)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=_cmd_validate)

    stats = subparsers.add_parser("stats", help="print feature statistics")
    stats.add_argument("dataset")
    stats.set_defaults(func=_cmd_stats)

    import_cmd = subparsers.add_parser("import", help="import a LeRobot v3 dataset")
    import_cmd.add_argument("source")
    import_cmd.add_argument("--format", choices=["lerobot"], default="lerobot")
    import_cmd.add_argument("--profile", required=True)
    import_cmd.add_argument("--source-class", choices=["public-real", "simulation"], required=True)
    import_cmd.add_argument("--out", required=True)
    import_cmd.add_argument("--repo-id", default=None)
    import_cmd.add_argument("--revision", default=None)
    import_cmd.add_argument("--license", default=None)
    import_cmd.add_argument("--public", action="store_true")
    import_cmd.add_argument("--no-images", action="store_true")
    import_cmd.add_argument("--created-at", default=None)
    import_cmd.add_argument("--dataset-id", default=None)
    import_cmd.set_defaults(func=_cmd_import)

    convert = subparsers.add_parser("convert", help="export a native dataset to LeRobot v3")
    convert.add_argument("dataset")
    convert.add_argument("--to", choices=["lerobot"], default="lerobot")
    convert.add_argument("--out", required=True)
    convert.add_argument("--mode", choices=["images", "videos"], default="images")
    convert.add_argument("--fps", type=int, default=None)
    convert.add_argument("--sample-policy", choices=["strict", "hold"], default="strict")
    convert.add_argument("--no-images", action="store_true")
    convert.set_defaults(func=_cmd_convert)

    report = subparsers.add_parser("report", help="render a quality report")
    report.add_argument("report")
    report.add_argument("--format", choices=["md", "json"], default="md")
    report.set_defaults(func=_cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "profile":
            if args.action == "show" and not args.profile_id:
                raise UsageError("profile show requires a profile id")
            return args.func(args)
        return args.func(args)
    except JchengError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
