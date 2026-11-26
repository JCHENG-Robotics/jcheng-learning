# M2 gradient-accumulation rehearsal (2026-11-26)

Status: **M2.0 configuration evidence, L1 offline GPU**. Not a policy-quality
result and not a hardware claim.

## 1. Question

The 6 GB RTX 3060 fits SmolVLA at batch 8 (MVE-0). Can it emulate the official
batch-64 fine-tune with `batch_size=8` and 8 gradient-accumulation steps, and
what does that cost?

## 2. Important `steps` semantics

In LeRobot 0.7, `--steps` counts **micro-batches**, not optimizer updates. With
`grad_accum=8`, `--steps 160` is 20 optimizer updates. An earlier `--steps 20`
run was only 2.5 updates and is not used for comparison.

`jcheng-train` records both `micro_steps` and `optimizer_steps`.

## 3. Setup

| Item | Value |
|---|---|
| Data | synthetic ArmPi train 3 eps / 240 frames; val 1 ep / 80 frames |
| Policy | `lerobot/smolvla_base` |
| Batch / grad accum / effective | 8 / 8 / 64 |
| Micro-steps / optimizer updates | 160 / 20 |
| Seed | 0 |
| GPU | RTX 3060 Laptop 6 GB |

## 4. Results

| Configuration | Updates | Wall clock (incl. load) | Peak VRAM | Final loss | Eval MAE | Eval RMSE |
|---|---:|---:|---:|---:|---:|---:|
| batch 8, no accum | 20 | 28.8 s | 3.53 GB | 1.199 | 0.4841 | 0.6379 |
| batch 8 × accum 8 | 20 | 105.9 s | 3.75 GB | 1.247 | 0.4948 | 0.6520 |

The effective-batch-64 run is ~3.7× the total wall clock (the 20 updates
themselves are ~8×; model load is fixed). On this synthetic 20-update run it is
slightly worse, which is expected noise on a tiny dataset and **not** a quality
claim. It demonstrates that 6 GB can reach effective batch 64 without OOM.

## 5. Files

- [train-record.json](train-record.json) — command, versions, dataset/checkpoint hashes.
- [train.log](train.log) — 160 micro-steps.
- [eval.json](eval.json) — aggregate held-out metrics.
- [samples.jsonl](samples.jsonl) — per-frame metrics.
- [SHA256SUMS](SHA256SUMS).

## 6. Limitations

- Synthetic data; 20 optimizer updates; no convergence or success claim.
- `--steps` micro-batch semantics must be stated in every M2 record.
- Batch 8 × accum 8 is memory-safe but not a speed win on 3060.
- No remote GPU comparison in this file; Orin is excluded from M2 training.
