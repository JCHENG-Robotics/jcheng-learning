# M2 rehearsal evidence — synthetic ArmPi (2026-11-26)

Status: **M2.0 pipeline rehearsal, L1 offline GPU**. This is not a useful
policy, not a success-rate result and not an M4 hardware claim. The checkpoint
lives outside the repository.

## 1. Scope

- Generate deterministic synthetic ArmPi data: train 3 episodes / 240 frames,
  validation 1 episode / 80 frames, 2 cameras, 64×48, 10 fps.
- Export both splits with `jcheng-dataset convert --mode images`.
- Run 20 official `lerobot-train` steps on `lerobot/smolvla_base` at batch 8.
- Run teacher-forced offline action-error evaluation on the held-out episode.
- Write a policy card with checkpoint hashes and limitations.
- No robot, camera, DDS, lease, `ExecuteMotion` or motion path.

## 1.1 Gates

| Gate | Result | Evidence |
|---|---|---|
| Unit/integration tests (current suite) | 68 passed | [pytest.txt](pytest.txt) |
| Repository gate | pass | [gate.txt](gate.txt) |

## 2. Environment

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3060 Laptop, 6144 MiB |
| Driver / CUDA | 595.99.02 / CUDA 13.2 |
| torch | 2.15.0+cu132 |
| lerobot | 0.7.0 |
| transformers | 5.22.2 |
| Model | `lerobot/smolvla_base` (Apache-2.0) |
| Batch / steps / seed | 8 / 20 / 0 |
| Peak allocated VRAM | 3.53 GB |

See [env.txt](env.txt).

## 3. Data

| Split | Native dataset | Native root SHA-256 | LeRobot export |
|---|---|---|---|
| Train | `synthetic-armpi_ultra-000003e9` | `sha256:a5ecace2d546bad86c44064b9bd1feadc5e991fbe9481f7be7f86694933d46c4` | `/tmp/m2-rehearsal-data/lerobot-train` |
| Validation | `synthetic-armpi_ultra-000007d2` | `sha256:69343e15fc13e7e2fd95065e9ad9be27a27b78e076a1c4ff5bfba7f9a1271007` | `/tmp/m2-rehearsal-data/lerobot-val` |

The data is synthetic (`source_class: synthetic`); no hardware claim applies.

## 4. Training result

- 20 optimizer steps completed; loss `4.972 → 1.199`; 20 steps ≈ 11 s after
  model load (train-record duration 28.8 s includes loading).
- Checkpoint: `/opt/jcheng/models/m2-rehearsal-20261126/checkpoints/000020/pretrained_model`.
- `model.safetensors` SHA-256:
  `sha256:14dee4d174de35a97e33f3c8832b1ed0b42e4e1d9a3059680386bcc2d6d633cb`.
- Full command, versions, data hashes and checkpoint file hashes:
  [train-record.json](train-record.json); log: [train.log](train.log).

## 5. Evaluation result

Teacher-forced offline action error on the held-out episode, 10 samples ×
50-step chunk × 6 dimensions, fixed inference seed 0:

| Metric | Value |
|---|---:|
| `action_mae` | 0.4841 rad |
| `action_rmse` | 0.6379 rad |
| `per_dim_mae` | `[0.5318, 0.2559, 0.2513, 0.4601, 0.4973, 0.9082]` |
| `n_samples` | 10 |
| `chunk_size` | 50 |

This is **not** a success rate, closed-loop result or deployment claim. The
protocol is [docs/m2/EVAL.md](../../docs/m2/EVAL.md) (v1, frozen before the run).
Full report: [eval.json](eval.json).

## 6. Artifact

[policy-card.json](policy-card.json) records the base model, checkpoint hashes,
dataset hashes, training parameters, evaluation metrics and limitations. The
weights are outside git under `/opt/jcheng/models/m2-rehearsal-20261126/`.

## 7. Limitations

- Synthetic data only; the policy is not useful and the metric cannot be
  extrapolated to ArmPi tasks.
- One 20-step run, no convergence study, no seed sweep, no hyper-parameter
  search.
- Teacher-forced offline error; no closed-loop success rate.
- Batch 8 fits (3.14 GB in MVE-0; 3.53 GB in training); batch 16 OOM; the
  exact boundary was not bisected.
- No hardware validation. M4 requires a separate, explicitly authorized
  supervised session.

## 8. Related

- [M2 plan](../../docs/m2/00-PLAN.md)
- [M2 evaluation protocol](../../docs/m2/EVAL.md)
- [MVE-0](../20261126_m2-mve0/README.md)
- [M1 evidence](../20261126_m1/README.md)
