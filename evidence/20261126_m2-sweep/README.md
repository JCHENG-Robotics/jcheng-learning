# M2 seed sweep — synthetic ArmPi (2026-11-26)

Status: **M2.0 pipeline-stability evidence, L1 offline GPU**. This is not a
policy-quality result and not a hardware claim.

## 1. Design

- Same deterministic synthetic data as the M2.0 rehearsal:
  train `synthetic-armpi_ultra-000003e9` (3 eps / 240 frames),
  validation `synthetic-armpi_ultra-000007d2` (1 ep / 80 frames).
- `lerobot/smolvla_base`, 20 optimizer steps, batch 8, seeds 0/1/2.
- Evaluation: 10 held-out frames × 50-step chunk × 6 dims, **inference seed 0**
  (fixed so metrics are comparable across checkpoints).
- A repeat seed-0 run checks whether the same seed reproduces the checkpoint.

## 2. Results

| Seed | Final loss | Action MAE (rad) | Action RMSE (rad) | model.safetensors |
|---:|---:|---:|---:|---|
| 0 | 1.199 | 0.4841 | 0.6379 | `sha256:14dee4d1…d633cb` |
| 1 | 1.298 | 0.5099 | 0.6832 | `sha256:6151fbd2…a306d1` |
| 2 | 1.265 | 0.4812 | 0.6329 | `sha256:2edde41c…987f80` |

Across the three seeds:

| Statistic | Value |
|---|---:|
| `action_mae` mean / pstdev | 0.4917 / 0.0129 rad |
| `action_rmse` mean / pstdev | 0.6513 / 0.0226 rad |
| final loss mean / pstdev | 1.254 / 0.041 |

These numbers show the harness is stable across seeds. They do **not** show a
useful policy; the data is synthetic and the run is 20 steps.

## 3. Repeatability

- A repeated seed-0 run produced the **same** `model.safetensors` SHA-256 and
  the same seeded evaluation metrics.
- The earlier unseeded eval differed between identical checkpoints because
  SmolVLA samples flow-matching noise. `jcheng-eval --seed 0` now fixes the
  inference seed; every reported metric in this directory uses it.
- Reproducibility claim: same code, lock, data hash, seed and eval seed →
  same checkpoint hash and metrics. GPU nondeterminism across different driver
  builds is not tested.

## 4. Per-sample data

Each `seedN-samples.jsonl` has one row per evaluated frame with
`action_mae_rad`, `action_rmse_rad`, `checkpoint_sha256`,
`dataset_info_sha256`, `seed` and `split`. These rows are the proposed input
to the benchmark suite in
[docs/m2/BENCHMARK-PROPOSAL.md](../../docs/m2/BENCHMARK-PROPOSAL.md).

## 4.1 Benchmark handoff

The draft L1 suite
[docs/m2/suites/m2-rehearsal-action-error-v1.yaml](../../docs/m2/suites/m2-rehearsal-action-error-v1.yaml)
was run with the real `jcheng-benchmark` harness over
`seed0-samples.jsonl`. The harness returned `inconclusive` (exit 2) because the
suite intentionally has no thresholds; it is informational, not a pass.
See [benchmark-rehearsal-report.json](benchmark-rehearsal-report.json) and
[benchmark-rehearsal-report.md](benchmark-rehearsal-report.md).

## 5. Limitations

- Synthetic data, 20 steps, 3 seeds: pipeline evidence only.
- Teacher-forced action error; no closed-loop success rate.
- Batch 8 fits (3.53 GB); batch 16 OOM; boundary not bisected.
- No robot, camera, DDS, lease or motion path was used.

## 6. Files

- [sweep.json](sweep.json) — machine-readable summary and stats.
- `seed{0,1,2}-train-record.json` — commands, versions, dataset and checkpoint hashes.
- `seed{0,1,2}-eval.json` — aggregate metrics.
- `seed{0,1,2}-samples.jsonl` — per-sample metrics.
- `seed0-repeat-eval.json`, `seed0-repeat-samples.jsonl` — repeated seed-0 run.
- `benchmark-rehearsal-report.{json,md}` — real benchmark harness output;
  `inconclusive` because thresholds are empty.
- [SHA256SUMS](SHA256SUMS) — checksums for this directory.

Related: [M2 plan](../../docs/m2/00-PLAN.md),
[frozen evaluation protocol](../../docs/m2/EVAL.md),
[M2.0 rehearsal](../20261126_m2-rehearsal/README.md).
