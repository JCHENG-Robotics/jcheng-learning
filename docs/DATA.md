# Dataset format and integrity — jcheng-learning

> Status: **Proposed** as of 2026-11-26; to be frozen at M1.
> Nothing here is implemented or accepted yet. No dataset is stored in this
> repository.

## 1. Storage boundary

Datasets live outside the repository, under an operator-selected root
(`JCHENG_DATASET_ROOT` in the operator environment; no absolute operator path
is committed). The repository holds only this specification, the validator and
aggregate evidence.

Rules:

- Episodes are write-once. A corrected export gets a new `dataset_id`; existing
  data is never edited in place.
- A dataset is referenced by `dataset_id` and the SHA-256 of its manifest.
- No recording, image, rosbag, MCAP or SQLite file enters git.
- Dataset licenses and consent are recorded per dataset; they are separate from
  the repository license.

## 2. Proposed layout

```text
<dataset-root>/
└── <dataset_id>/
    ├── dataset.yaml            # manifest (this document)
    ├── SHA256SUMS              # one line per file, sorted
    └── episodes/
        └── <episode_id>/
            ├── meta.json       # start/end time, operator session, robot profile
            ├── observations/   # exported streams, read-only
            ├── commands/       # commanded values, explicitly labelled
            ├── measurements/   # bus-read positions when pose truth is needed
            └── labels/         # task, phase and outcome annotations
```

The exact file formats are an M1 decision. The directory contract above is the
part that the validator and the documentation agree on.

## 3. Manifest fields (draft)

| Field | Meaning |
|---|---|
| `schema_version` | manifest schema version, integer |
| `dataset_id` | immutable identifier, unique per export |
| `created_at` | ISO 8601 timestamp with timezone |
| `source` | capture session identifier, robot profile and software commit |
| `contract_hash` | `jcheng-interfaces` contract hash in force at capture |
| `episodes` | count, each `episode_id` and duration |
| `streams` | topic/file name, message type, nominal rate, time source |
| `calibration` | camera/wrist/extrinsic calibration identifiers used |
| `annotations` | task name, phase labels, outcome labels |
| `integrity` | SHA-256 of `SHA256SUMS`, total file count, total bytes |
| `consent_and_license` | dataset license and any operator/people consent note |

## 4. Provenance and truth rules

These rules exist because the ArmPi stack has no encoders, no IMU and no joint
feedback on the ROS side that can be trusted as measurement:

1. **Commanded and measured data are separate directories.** `/joint_states`
   from the vendor stack is a command cache, not a measurement. A dataset that
   needs pose truth must carry a `GetBusServoState` bus read in `measurements/`.
2. **No fabricated fill.** Missing depth, TF or joint state is recorded as
   missing. The exporter must not interpolate, hold or zero-fill and present the
   result as observed data.
3. **Timestamps are recorded, not reconstructed.** Each stream records its
   source clock and the host clock offset when available. A clock jump or a
   non-monotonic span is an integrity failure, not a value to be silently
   rebased.
4. **TF is recorded as published.** The exporter does not rebuild the wrist
   chain from the stock URDF or from `camera_optical_calibrated`.
5. **Calibration identifiers are mandatory.** A dataset without the calibration
   identifiers used at capture cannot support a metric evaluation.
6. **Phase labels follow the task.** Labels describe observed task phases; they
   are not inferred from the policy under evaluation.

## 5. Integrity gate

The M1 validator must check, at minimum:

| Check | Failure action |
|---|---|
| Manifest parses and matches the declared schema | reject |
| `SHA256SUMS` covers every file and matches | reject |
| Episode count and durations match the manifest | reject |
| Timestamps are monotonic within each stream, gaps within the declared bound | reject |
| No duplicate `(stream, timestamp)` pairs | reject |
| Every referenced calibration identifier exists | reject |
| Commanded, measured and label directories are internally consistent | reject |

Rejection is terminal for that `dataset_id`. The operator re-exports, and the
new export gets a new identifier. A validator bug is fixed in the repository
and the dataset is re-validated; the old result is kept in the evidence record.

## 6. Privacy and licensing

- Recordings of people require consent; datasets without a recorded consent
  note are not used for training.
- Datasets and model artifacts carry their own licenses. The repository's
  eventual license does not cover them.
- Vendor data or vendor model weights are not copied into a dataset or a
  repository artifact.
- Retention and deletion are operator decisions recorded per dataset. Removing
  a dataset does not rewrite published evidence; the evidence records that the
  dataset was withdrawn.

## 7. M1 exit criteria

- The layout and manifest fields above are frozen in this document.
- A ROS-free validator and its tests exist and run in CI.
- One exported episode set is accepted, and one deliberately corrupted copy is
  rejected, with both results recorded under `evidence/`.
- No robot access is used, and no data enters git.
