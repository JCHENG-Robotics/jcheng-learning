# Dataset format and integrity — jcheng-learning

> Status: **Frozen at M1 (2026-11-26)**, version 0.2.0. The normative contract
> is [docs/m1/04-DATA-CONTRACT.md](m1/04-DATA-CONTRACT.md); this file is the
> repository-level summary. If the two differ, the M1 contract wins.
> No dataset is stored in this repository.

## 1. Storage boundary

Datasets live outside the repository, under an operator-selected root
(`JCHENG_DATASET_ROOT` in the operator environment; no absolute operator path
is committed). The repository holds the specification, the validator and
aggregate evidence only.

Rules:

- Episodes are write-once. A corrected export gets a new `dataset_id`; existing
  data is never edited in place.
- A dataset is referenced by `dataset_id` and the SHA-256 of its `SHA256SUMS`.
- No recording, image, rosbag, MCAP or SQLite file enters git.
- Dataset licenses and consent are recorded per dataset; they are separate from
  the repository license.

## 2. Layout

```text
<dataset-root>/
└── <dataset_id>/
    ├── dataset.yaml            # jcheng.dataset.v1
    ├── provenance.json         # jcheng.provenance.v1
    ├── SHA256SUMS              # covers every file except itself
    └── episodes/
        └── <episode_id>/
            ├── meta.json       # jcheng.episode.v1
            ├── frames.jsonl    # one frame per line
            ├── images/
            │   └── <camera>/<frame:06d>.png
            ├── measurements.jsonl   # optional bus reads
            └── labels.jsonl         # optional phase labels
```

`dataset.yaml` records the robot profile, action/state space IDs, ordered joint
names, per-dimension units, timing, cameras, episode counts/tasks and the
source class. `provenance.json` records the origin, software/lock, calibration,
license and transformation history. `frames.jsonl` records per-frame state,
action, truth and image references with session-monotonic nanosecond stamps.

## 3. Provenance and truth rules

1. **Commanded and measured data are separate.** `/joint_states` from the
   vendor stack is a command cache, not a measurement. A dataset that needs
   pose truth must declare `state.truth_source=bus_read` and carry a
   `GetBusServoState` bus read in `measurements.jsonl`.
2. **No fabricated fill.** Missing depth, TF or joint state is recorded as
   missing. The exporter must not interpolate, hold or zero-fill and present
   the result as observed data.
3. **Timestamps are recorded, not reconstructed.** Each stream records its
   source clock; a clock jump or non-monotonic span is an integrity failure.
4. **TF is recorded as published.** The exporter does not rebuild the wrist
   chain from the stock URDF or from `camera_optical_calibrated`.
5. **Calibration identifiers are mandatory for own-real data.** A dataset
   without the calibration identifiers used at capture cannot support a metric
   evaluation.
6. **Phase labels follow the task.** Labels describe observed task phases; they
   are not inferred from the policy under evaluation.

## 4. Integrity gate

The M1 validator (`jcheng_learning.validate`) checks at minimum:

| Check | Failure action |
|---|---|
| Manifest parses and matches the declared schema | reject |
| `SHA256SUMS` covers every file and matches | reject |
| Episode count, frame count and durations match the manifest | reject |
| Timestamps are monotonic, finite and within jitter/skew bounds | reject |
| No duplicate `(stream, timestamp)` pairs | reject |
| Joint names/order/dimensions match the profile | reject |
| Units are declared; own/sim/synthetic are SI | reject |
| NaN/Inf, action jumps and limit violations | reject |
| Required images exist, decode, match shape and are non-blank | reject |
| Provenance class fields, license and `truth_source` are consistent | reject |

A failed dataset is terminal. The operator re-exports under a new
`dataset_id`; the old result is kept in the evidence record. The full report is
`jcheng.dataset-quality-report.v1` (JSON) with a Markdown rendering.

## 5. Privacy and licensing

- Recordings of people require consent; datasets without a recorded consent
  note are not used for training.
- Datasets and model artifacts carry their own licenses. The repository's
  eventual license does not cover them.
- Vendor data or vendor model weights are not copied into a dataset or a
  repository artifact.
- Retention and deletion are operator decisions recorded per dataset.

## 6. M1 exit criteria (met)

- The native layout and manifest fields are frozen in
  [docs/m1/04-DATA-CONTRACT.md](m1/04-DATA-CONTRACT.md).
- A ROS-free validator, CLI and tests exist and run in CI.
- A deterministic synthetic set is accepted, and 17 injected anomalies are
  rejected, with results under `evidence/20261126_m1/`.
- No robot access is used and no data enters git.
