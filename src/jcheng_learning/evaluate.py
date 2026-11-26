"""Offline, teacher-forced action-error evaluation for an M2 rehearsal.

This is not a closed-loop evaluation and not a success-rate claim. It loads a
checkpoint, predicts an action chunk for held-out frames and compares it with
the recorded action chunk.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .errors import DatasetError, DependencyError
from .io.hashing import file_sha256
from .version import __version__


def _version(name: str) -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "unknown"


def _rename_cameras(sample: dict[str, Any], count: int) -> dict[str, Any]:
    result = dict(sample)
    image_keys = sorted(
        key for key in result if key.startswith("observation.images.")
    )
    for index, key in enumerate(image_keys[:count]):
        result[f"observation.images.camera{index + 1}"] = result.pop(key)
    return result


def evaluate_checkpoint(
    *,
    checkpoint: Path,
    val_root: Path,
    out: Path,
    samples: int = 10,
    seed: int = 0,
    jsonl_out: Path | None = None,
) -> dict[str, Any]:
    try:
        import torch
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    except ImportError as exc:  # pragma: no cover - compat env
        raise DependencyError("lerobot[dataset,smolvla] and torch are required") from exc
    if not torch.cuda.is_available():
        raise DependencyError("CUDA is not available")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    info = json.loads((Path(val_root) / "meta" / "info.json").read_text(encoding="utf-8"))
    fps = int(info["fps"])
    policy = SmolVLAPolicy.from_pretrained(str(checkpoint)).to("cuda").eval()
    chunk = int(policy.config.chunk_size)
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        str(checkpoint),
        preprocessor_overrides={"device_processor": {"device": "cuda"}},
    )
    dataset = LeRobotDataset(
        "local/m2-val",
        root=Path(val_root),
        delta_timestamps={"action": [i / fps for i in range(chunk)]},
    )
    camera_count = len(
        [key for key in info["features"] if key.startswith("observation.images.")]
    )
    total = min(samples, len(dataset))
    per_dim: list[list[float]] = []
    abs_errors: list[float] = []
    samples_rows: list[dict[str, Any]] = []
    checkpoint_sha = (
        "sha256:" + file_sha256(Path(checkpoint) / "model.safetensors")
        if (Path(checkpoint) / "model.safetensors").is_file()
        else None
    )
    dataset_info_sha = "sha256:" + file_sha256(Path(val_root) / "meta" / "info.json")
    for index in range(total):
        sample = _rename_cameras(dict(dataset[index]), camera_count)
        ground_truth = sample["action"]
        infer = {key: value for key, value in sample.items() if key != "action"}
        batch = preprocess(infer)
        with torch.inference_mode():
            prediction = postprocess(policy.predict_action_chunk(batch))
        if prediction.ndim == 3:
            prediction = prediction[0]
        prediction = prediction.detach().float().cpu().numpy()
        truth = np.asarray(ground_truth, dtype=np.float32)
        if truth.ndim == 3:
            truth = truth[0]
        steps = min(prediction.shape[0], truth.shape[0])
        prediction = prediction[:steps]
        truth = truth[:steps]
        error = prediction - truth
        abs_errors.extend(np.abs(error).reshape(-1).tolist())
        dim_mae = np.abs(error).mean(axis=0)
        if not per_dim:
            per_dim = [[] for _ in range(dim_mae.size)]
        for dim, value in enumerate(dim_mae):
            per_dim[dim].append(float(value))
        samples_rows.append(
            {
                "schema": "jcheng.m2.eval.sample.v1",
                "sample_id": f"seed{seed}-sample{index:04d}",
                "sample_index": index,
                "split": "held_out",
                "seed": seed,
                "steps": steps,
                "action_dim": int(dim_mae.size),
                "action_mae_rad": float(np.abs(error).mean()),
                "action_rmse_rad": float(np.sqrt((error**2).mean())),
                "checkpoint_sha256": checkpoint_sha,
                "dataset_info_sha256": dataset_info_sha,
            }
        )
    if not abs_errors:
        raise DatasetError("evaluation produced no samples")
    metrics = {
        "action_mae": float(np.mean(abs_errors)),
        "action_rmse": float(
            np.mean([row["action_rmse_rad"] for row in samples_rows])
        ),
        "per_dim_mae": [float(np.mean(values)) for values in per_dim],
        "n_samples": total,
        "chunk_size": chunk,
        "action_dim": len(per_dim),
    }
    payload: dict[str, Any] = {
        "schema": "jcheng.m2.eval.v1",
        "date": datetime.now(timezone.utc).isoformat(),
        "tool": {
            "jcheng_learning": __version__,
            "lerobot": _version("lerobot"),
            "torch": _version("torch"),
            "python": sys.version.split()[0],
        },
        "checkpoint": str(checkpoint),
        "seed": seed,
        "val_dataset": {
            "root": str(val_root),
            "info_sha256": file_sha256(Path(val_root) / "meta" / "info.json"),
            "features": sorted(info["features"]),
            "fps": fps,
        },
        "metrics": metrics,
        "limitations": [
            "Teacher-forced offline action error; not closed-loop control.",
            "No success rate, no hardware and no safety claim.",
            "Synthetic training dataset; this is a pipeline rehearsal, not a useful policy.",
        ],
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if jsonl_out is not None:
        jsonl_out = Path(jsonl_out)
        jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_out.open("w", encoding="utf-8", newline="\n") as handle:
            for row in samples_rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        payload["samples_jsonl"] = str(jsonl_out)
    return payload


def _cmd_eval(args: argparse.Namespace) -> int:
    payload = evaluate_checkpoint(
        checkpoint=Path(args.checkpoint),
        val_root=Path(args.dataset),
        out=Path(args.out),
        samples=args.samples,
        seed=args.seed,
        jsonl_out=Path(args.jsonl) if args.jsonl else None,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jcheng-eval")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--jsonl", default=None, help="write per-sample JSONL")
    args = parser.parse_args(argv)
    try:
        return _cmd_eval(args)
    except (DatasetError, DependencyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
