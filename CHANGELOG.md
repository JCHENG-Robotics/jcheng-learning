# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- M2.0 rehearsal harness: `jcheng-train` wraps the official `lerobot-train`,
  `jcheng-eval` computes teacher-forced action error, and the policy card
  records checkpoint hashes and limitations.
- MVE-0 evidence: SmolVLA batch 8 fits the 6 GB GPU; batch 16 OOM.
- M2.0 rehearsal evidence: 20 steps on synthetic ArmPi, offline MAE/RMSE,
  policy card. No hardware and no policy-quality claim.
- M2 multi-seed stability sweep (0/1/2) with a fixed evaluation seed and
  per-sample JSONL.
- Draft benchmark suites (`m2-rehearsal-action-error-v1`,
  `m2-action-error-v1`) and a benchmark handoff proposal; benchmark repository
  is not modified.
- Gradient-accumulation rehearsal: batch 8 × 8 (effective 64), 20 optimizer
  updates = 160 micro-batches; `jcheng-train` now records both counts and
  accepts `--updates`.

## [0.2.0] — 2026-11-26

### Added

- Native dataset contract (`jcheng.dataset.v1`, `jcheng.episode.v1`,
  `jcheng.provenance.v1`) with immutable `dataset_id`, `SHA256SUMS`,
  per-stream timestamps, commanded/measured separation and source classes.
- Native reader/writer, deterministic synthetic generator and `jcheng-dataset`
  CLI (`synth`, `inspect`, `validate`, `stats`, `report`, `import`, `convert`,
  `hash`).
- Robot profiles for ArmPi Ultra, Gate-2, Piper X, SO-101 (import only),
  PushT 2D and a probe fixture.
- `DQ-*` validator, quality report schema and Markdown renderer.
- LeRobot Dataset v3.0 reader and importer (pyarrow, no torch) and an exporter
  using the official `LeRobotDataset` writer.
- M1 evidence: synthetic determinism, pusht and SO-101 round-trips, 17-case
  anomaly matrix.

### Changed

- Version `0.1.0` → `0.2.0`.
- `README.md` / `README.zh-CN.md` now describe the M1 offline infrastructure.
- Repository gate runs tests in a locked `uv` environment outside the tree.

### Verified

- 65 unit/integration tests pass; 4 no-hardware tests pass; M0 regression passes.
- pusht 206 eps / 25,650 frames and SO-101 50 eps / 11,939 frames import with
  exact state/action values.
- Synthetic image round-trip has pixel diff 0; 17 injected anomalies are
  detected. See `evidence/20261126_m1/`.

## [0.1.0] — 2026-11-26

### Added

- Initial repository scaffold: bilingual documentation set, admission manifest,
  repository gate, no-hardware static scan and `learning-gate` CI.
- Offline-first boundary for datasets, training runs, model artifacts and a
  future skill-intent surface. No runtime node, no policy and no hardware
  access.
- Organization documentation set: `README.md`, `README.zh-CN.md`, `ROADMAP.md`,
  `ACCEPTANCE.md` and this changelog.
