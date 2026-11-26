# Acceptance report — jcheng-learning

> Status: **pass (L1)** as of 2026-11-26 for v0.2.0, M1 scope.
> Operator: JerichoCheng. Reviewer: pending.
> Scope: offline dataset schema, native store, validator, CLI, LeRobot v3
> reader/importer/exporter, synthetic generator and evidence.
> No training run, policy, runtime node, device or motion command exists.
> No robot was contacted.

## 1. Gates

| Gate | Command | Level | Result | Evidence |
|---|---|---|---|---|
| Repository gate | `bash scripts/check_repo_gate.sh` | L0 | pass | `evidence/20261126_m1/gate.txt` |
| Unit/integration tests | `uv run --frozen --extra test python -m pytest -q` | L1 | pass (65 tests) | `evidence/20261126_m1/pytest.txt` |
| No-hardware static tests | `pytest -q -v tests/test_no_hardware.py` | L0 | pass (4 tests) | `evidence/20261126_m1/no-hardware.txt` |
| M0 regression | original 13 tests | L0/L1 | pass | `evidence/20261126_m1/pytest.txt` |
| Synthetic quality | `jcheng-dataset validate` | L1 | pass | `evidence/20261126_m1/synthetic-quality.json` |
| Public import (pusht) | `jcheng-dataset import` + `validate` | L1 | pass (206 eps / 25,650 frames) | `evidence/20261126_m1/pusht-quality.json` |
| Public import (SO-101) | `jcheng-dataset import` + `validate` | L1 | inconclusive (gripper range unknown) | `evidence/20261126_m1/so101-quality.json` |
| LeRobot round-trip (synthetic) | official `LeRobotDataset` load | L1 | pass; state/action/image diff 0 | `evidence/20261126_m1/synthetic-roundtrip.json` |
| LeRobot round-trip (SO-101) | official `LeRobotDataset` load | L1 | pass; state/action diff 0 | `evidence/20261126_m1/so101-roundtrip.json` |
| Anomaly matrix | 17 injected cases | L1 | pass; each expected `DQ-*` fails | `evidence/20261126_m1/anomaly-matrix.json` |
| Mock integration | — | L2 | not applicable (no runtime) | — |
| Replay | — | L4 | not applicable (no policy) | — |
| Hardware | — | L5 | not applicable; no session authorized | — |

## 2. Verified claims

| Claim | Level | Evidence |
|---|---|---|
| The native schema validates and the writer/reader round-trips without data loss | L1 | `tests/test_native_roundtrip.py`; `evidence/20261126_m1/pytest.txt` |
| Synthetic output is deterministic for a fixed seed, `created_at` and lock | L1 | `tests/test_synthetic.py`; identical `root_sha256` |
| `lerobot/pusht` imports with exact state/action values | L1 | 206 eps / 25,650 frames; max diff 0; `pusht-quality.json`, `pusht-diff.json` |
| `lerobot/svla_so101_pickplace` imports and exports with exact tabular values | L1 | 50 eps / 11,939 frames; max diff 0; `so101-roundtrip.json` |
| The LeRobot v3 reader works without torch | L1 | core tests; pyarrow-only reader |
| The official writer produces a loadable v3 dataset (images and tabular) | L1 | U2 probe; synthetic and SO-101 round-trips |
| 17 anomalies are detected with the expected check ID and exit code 1 | L1 | `anomaly-matrix.json` |
| No device, vendor topic or motion service exists in the tree | L0 | `tests/test_no_hardware.py`; `no-hardware.txt` |
| The core path has no torch, ROS, GPU or network dependency | L0/L1 | `pyproject.toml`; core tests; `pytest.txt` |
| The M0 document set, manifest and CI still pass | L0/L1 | `gate.txt`; `pytest.txt` |

## 3. Not verified

| Item | Reason | Risk |
|---|---|---|
| Offline training and evaluation | Not implemented (M2) | No policy or metric exists |
| Inference intent behavior | Not implemented (M3) | No runtime surface |
| Full SO-101 image import | AV1 video was decoded (U1) but the 11,939-frame image import was not run | Image path on real public video is only partially exercised |
| SO-101 gripper semantics | Public data has no gripper range | Report is `inconclusive`, not pass |
| Video-mode export | Only image-mode export was run | `videos` mode remains unverified (U7) |
| 6 GB GPU training | Not attempted | M2 must measure before committing to SmolVLA |
| Hardware behavior | No session; no inference node | Nothing to validate on the robot |

## 4. Limitations

- M1 is offline. It never opens a camera, serial, CAN or GPIO device and never
  joins a DDS domain.
- The SO-101 quality report is intentionally `inconclusive`: an unknown gripper
  range cannot become a pass.
- The synthetic and public datasets live outside the repository; only summaries
  and reports are checked in.
- Image-mode LeRobot datasets embed image bytes in Parquet; the final dataset
  has no `images/` directory. Pixel equality is checked from the embedded image.
- No `LICENSE` file exists; the organization license review is still open.
- No e-stop, brake, encoder or self-collision model exists on the platform. A
  software stop is not an e-stop.
- This report is an operator acceptance of M1, not an organization-wide or
  hardware acceptance.

## 4.1 Implementation deviations (recorded, intentional)

- Manifest/episode/provenance/profile/action-map use code-level validators; only
  the quality report has a standalone JSON Schema. Formal JSON Schemas for the
  data contract are an M2 interfaces item.
- `--sample-policy hold` is rejected in M1; only `strict` is implemented.
- `jcheng-dataset import` implements LeRobot v3 only; historical native data is
  read and validated directly, without a separate legacy adapter.
- `videos` export exists but is unverified (U7); M1 acceptance uses `images`.
- Two extra profiles (`pusht_2d`, `probe_2d`) exist only for the public
  benchmark and the test fixture; the production robot profiles remain four.

## 4.2 Post-M1 note

Three M2 harness tests were added after this M1 snapshot (current suite: 68).
They exercise the `jcheng-train`/`jcheng-eval` modules without torch and are not
an M1 claim. The M1 counts above remain the 2026-11-26 snapshot.

## 5. Sign-off

| Role | Name | Date |
|---|---|---|
| Operator | JerichoCheng | 2026-11-26 |
| Reviewer | pending | — |

## 6. Machine-readable report

None. The M1 quality reports validate against
`src/jcheng_learning/schemas/jcheng.dataset-quality-report.v1.schema.json` and
are stored under `evidence/20261126_m1/`. When an ecosystem acceptance report is
produced, it must validate against
`jcheng-interfaces/schemas/acceptance-report.v1.schema.json`.
