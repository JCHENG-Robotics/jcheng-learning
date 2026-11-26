"""M2 offline training rehearsal harness.

This module wraps the official ``lerobot-train`` CLI, records a reproducible
run record and hashes the resulting checkpoint. It does not train on the robot
and does not promote a policy.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import DatasetError, UsageError
from .io.hashing import file_sha256
from .lerobot import LeRobotV3Reader
from .provenance import git_info, lock_sha256, repo_root
from .version import __version__


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "unknown"


def _checkpoint_dir(out: Path, steps: int) -> Path:
    candidate = out / "checkpoints" / f"{steps:06d}" / "pretrained_model"
    if candidate.is_dir():
        return candidate
    candidates = sorted(out.glob("checkpoints/*/pretrained_model"))
    if not candidates:
        raise DatasetError(f"no checkpoint under {out / 'checkpoints'}")
    return candidates[-1]


def _checkpoint_hashes(checkpoint: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(checkpoint.rglob("*")):
        if path.is_file():
            hashes[path.relative_to(checkpoint).as_posix()] = file_sha256(path)
    return hashes


def train_rehearsal(
    *,
    train_root: Path,
    out: Path,
    steps: int = 20,
    batch_size: int = 8,
    grad_accum: int = 1,
    seed: int = 0,
    policy_path: str = "lerobot/smolvla_base",
    timeout_s: int = 900,
) -> dict[str, Any]:
    if steps < 1 or batch_size < 1 or grad_accum < 1:
        raise UsageError("steps, batch_size and grad_accum must be positive")
    reader = LeRobotV3Reader(train_root)
    dataset_id = train_root.name
    provenance_path = train_root / "jcheng" / "provenance.json"
    if provenance_path.is_file():
        try:
            dataset_id = json.loads(provenance_path.read_text(encoding="utf-8"))["dataset_id"]
        except (json.JSONDecodeError, KeyError):
            pass
    cameras = [key.split(".")[-1] for key in reader.image_keys]
    if not cameras:
        raise DatasetError("training dataset has no cameras")
    rename_map = {
        f"observation.images.{key}": f"observation.images.camera{index + 1}"
        for index, key in enumerate(cameras)
    }
    empty_cameras = max(0, 3 - len(cameras))
    out = Path(out)
    if out.exists():
        raise DatasetError(f"output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    executable = Path(sys.executable).with_name("lerobot-train")
    lerobot_train = str(executable) if executable.is_file() else "lerobot-train"
    command = [
        lerobot_train,
        f"--policy.path={policy_path}",
        "--policy.repo_id=local/m2-rehearsal",
        "--policy.push_to_hub=false",
        f"--policy.empty_cameras={empty_cameras}",
        "--policy.device=cuda",
        f"--dataset.repo_id=local/{dataset_id}",
        f"--dataset.root={train_root}",
        f"--rename_map={json.dumps(rename_map, separators=(',', ':'))}",
        f"--batch_size={batch_size}",
        f"--accelerator.gradient_accumulation.steps={grad_accum}",
        f"--steps={steps}",
        "--num_workers=0",
        f"--save_freq={steps}",
        "--log_freq=1",
        f"--output_dir={out}",
        "--job_name=m2-rehearsal",
        "--trackio.enable=false",
        f"--seed={seed}",
    ]
    commit, dirty = git_info()
    started = datetime.now(timezone.utc).isoformat()
    started_monotonic = time.monotonic()
    result = subprocess.run(
        command,
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    duration = round(time.monotonic() - started_monotonic, 3)
    out.mkdir(exist_ok=True)
    log = out / "train.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    record: dict[str, Any] = {
        "schema": "jcheng.m2.train-record.v1",
        "tool": {
            "jcheng_learning": __version__,
            "lerobot": _pkg_version("lerobot"),
            "torch": _pkg_version("torch"),
            "git_commit": commit,
            "git_dirty": dirty,
            "lock_sha256": lock_sha256(),
            "python": sys.version.split()[0],
        },
        "dataset": {
            "dataset_id": dataset_id,
            "root": str(train_root),
            "info_sha256": file_sha256(train_root / "meta" / "info.json"),
            "profile": reader.robot_type,
            "episodes": reader.total_episodes,
            "frames": reader.total_frames,
            "cameras": cameras,
        },
        "run": {
            "command": command,
            "steps": steps,
            "micro_steps": steps,
            "optimizer_steps": steps // grad_accum,
            "batch_size": batch_size,
            "grad_accum": grad_accum,
            "effective_batch_size": batch_size * grad_accum,
            "seed": seed,
            "policy_path": policy_path,
            "empty_cameras": empty_cameras,
            "rename_map": rename_map,
            "started_at": started,
            "duration_s": duration,
            "returncode": result.returncode,
            "log": str(log),
        },
    }
    if result.returncode != 0:
        record["result"] = "fail"
        record["error"] = (result.stderr or result.stdout)[-2000:]
        (out / "train-record.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        raise DatasetError(
            f"training rehearsal failed with exit {result.returncode}; see {log}"
        )
    checkpoint = _checkpoint_dir(out, steps)
    record["result"] = "pass"
    record["checkpoint"] = {
        "path": str(checkpoint),
        "files": _checkpoint_hashes(checkpoint),
    }
    (out / "train-record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def _cmd_rehearsal(args: argparse.Namespace) -> int:
    if args.steps is not None and args.updates is not None:
        raise UsageError("use either --steps (micro-batches) or --updates, not both")
    steps = (
        args.updates * args.grad_accum
        if args.updates is not None
        else (args.steps if args.steps is not None else 20)
    )
    record = train_rehearsal(
        train_root=Path(args.train),
        out=Path(args.out),
        steps=steps,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        seed=args.seed,
        policy_path=args.policy,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jcheng-train")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    rehearsal = sub.add_parser("rehearsal", help="short official LeRobot training run")
    rehearsal.add_argument("--train", required=True, help="LeRobot v3 dataset root")
    rehearsal.add_argument("--out", required=True)
    rehearsal.add_argument(
        "--steps", type=int, default=None,
        help="micro-batches (LeRobot semantics); prefer --updates",
    )
    rehearsal.add_argument(
        "--updates", type=int, default=None,
        help="optimizer updates; converted to micro-batches = updates * grad-accum",
    )
    rehearsal.add_argument("--batch-size", type=int, default=8)
    rehearsal.add_argument("--grad-accum", type=int, default=1)
    rehearsal.add_argument("--seed", type=int, default=0)
    rehearsal.add_argument("--policy", default="lerobot/smolvla_base")
    rehearsal.set_defaults(func=_cmd_rehearsal)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DatasetError as exc:
        print(f"DatasetError: {exc}", file=sys.stderr)
        return exc.exit_code
    except UsageError as exc:
        print(f"UsageError: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
