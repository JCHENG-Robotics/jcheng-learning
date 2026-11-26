# jcheng-learning

**English** | [简体中文](README.zh-CN.md)

> Status: **Experimental** as of 2026-11-26. Version 0.2.0.
> M1 offline dataset infrastructure: the repository defines and validates the
> dataset contract, converts public LeRobot v3 datasets to the native store and
> exports the native store through the official LeRobot writer. It still has no
> runtime node, no policy, no device access and no motion authority.
> English canonical; the Chinese README is a translation.

`jcheng-learning` is the L3 learning capability of the JCHENG ecosystem. Its
charter is to turn recorded robot episodes into versioned datasets, train and
evaluate policies offline, and — only from M3 — publish skill **intent** for the
system layer to validate and execute. It never drives a device, never rebuilds
motion itself and never bypasses `jcheng-system`.

## Scope and boundary

| Item | This repository |
|---|---|
| Layer | L3 capability (`capability.yaml`) |
| Inputs | Recorded episodes exported by an operator, public LeRobot v3 datasets, deterministic synthetic data |
| Outputs | Immutable native datasets (`jcheng.dataset.v1`), quality reports, LeRobot v3 exports, and model artifacts from M2 |
| Motion authority | None in v0.2.0 (`safety.class: offline`, empty runtime surface) |
| Hardware access | `none` |
| Owned devices | none |
| Forbidden | device access, vendor topics, `/cmd_vel`, `/move_action`, `ExecuteMotion`, fabricated sensor data, datasets or model weights in git |

The system layer is the only origin of motion. The perception layer is the only
source of advisory targets. A policy produced here may propose an action; the
system layer applies the control lease, deadman, limits and the stop latch
before anything moves.

## M1 capabilities (v0.2.0)

- **Dataset contract** — `jcheng.dataset.v1` / `jcheng.episode.v1` /
  `jcheng.provenance.v1`; immutable `dataset_id`, `SHA256SUMS`, per-stream
  timestamps, commanded/measured separation and `source_class`
  (`synthetic / simulation / public-real / own-real`).
- **Robot profiles** — ArmPi Ultra, Gate-2, Piper X and SO-101 (import only),
  plus PushT 2D and a probe fixture. Profiles are data, not code branches.
- **Validator** — the `DQ-*` gate covers layout, hashes, time, joint order,
  dimensions, units, gripper conventions, limits, NaN/Inf, images and
  provenance. It never repairs a dataset.
- **Action-space mapping** — explicit per-dimension affine rules
  (`action_map.py`), including the ArmPi raw `r_joint` → canonical gripper map;
  no implicit reordering or unit change.
- **Adapters** — a read-only LeRobot v3 reader (pyarrow, no torch), a public
  importer to the native store, and an exporter that calls the official
  `LeRobotDataset.create/add_frame/save_episode/finalize`.
- **CLI** — `jcheng-dataset synth|inspect|validate|stats|report|import|convert|hash`
  with stable exit codes `0/1/2/3/4`.
- **Deterministic synthetic data** — same seed, fixed `created_at` and locked
  dependencies produce the same `root_sha256`.

The design and the frozen data contract are in [docs/m1/](docs/m1/00-INDEX.md).
M1 evidence is in [evidence/20261126_m1/](evidence/20261126_m1/README.md).

## Repository layout

```text
jcheng-learning/
├── pyproject.toml                 # package, console script, extras, pytest config
├── uv.lock                        # locked core/test/video/lerobot resolution
├── capability.yaml                # admission manifest (offline, hardware_access: none)
├── src/jcheng_learning/
│   ├── cli.py                     # jcheng-dataset
│   ├── native/                    # native reader/writer
│   ├── lerobot/                   # v3 reader, importer, exporter
│   ├── validate/                  # DQ-* engine and report
│   ├── profiles/                  # robot-adapter.yaml files + registry
│   └── schemas/                   # JSON Schema files
├── tests/                         # unit, CLI, native, LeRobot reader/import tests
├── docs/
│   ├── ARCHITECTURE.md            # data, training and inference planes
│   ├── DATA.md                    # dataset layout, provenance and integrity rules
│   ├── INTEGRATION.md             # admission, lease and failure semantics
│   ├── m1/                        # M1 design package (Chinese)
│   └── m2/                        # M2 plan and frozen evaluation protocol
├── evidence/20261126_scaffold/    # M0 evidence record
├── evidence/20261126_m1/          # M1 offline evidence record
├── VERSION / CHANGELOG.md / ACCEPTANCE.md / ROADMAP.md
└── LICENSE-REVIEW.md
```

## Requirements

- Python 3.12 and `uv` 0.13.x for the locked environment.
- Core: `PyYAML`, `pyarrow`, `numpy`, `Pillow`, `jsonschema`,
  `huggingface_hub`. No ROS, no torch and no GPU for the core path.
- Optional `video` extra: `av==15.1.0` for AV1/MP4 decode.
- Optional `lerobot` extra: `lerobot[dataset]==0.7.0` for the official writer
  and compatibility oracle. It pulls torch; the core CI does not install it.
- Operator-side storage for datasets and model artifacts, outside this
  repository. Weight files belong in `/opt/jcheng/models/`; recordings and
  datasets never enter git.

## Quick start

```bash
# Core environment (no torch)
uv sync --frozen --extra test

# Generate and validate a deterministic synthetic dataset
uv run jcheng-dataset synth --profile armpi_ultra --out /tmp/jcheng-m1 \
  --episodes 2 --frames 8 --fps 10 --seed 0 --image-size 64x48
uv run jcheng-dataset validate /tmp/jcheng-m1/synthetic-armpi_ultra-00000000

# Tests and gate
uv run --frozen --extra test python -m pytest -q
bash scripts/check_repo_gate.sh
```

LeRobot export requires the optional extra:

```bash
uv sync --frozen --extra lerobot --extra video
uv run --extra lerobot jcheng-dataset convert /tmp/jcheng-m1/synthetic-armpi_ultra-00000000 \
  --to lerobot --out /tmp/jcheng-m1-export --mode images
```

The operator-run compatibility suite is in [compat/](compat/README.md).

## Validation status

| Claim | Status | Evidence |
|---|---|---|
| Repository gate and unit tests pass | Verified (L0/L1, 2026-11-26) | [evidence/20261126_m1/](evidence/20261126_m1/README.md) |
| M0 scaffold and admission manifest | Verified (L0/L1, 2026-11-26) | `evidence/20261126_scaffold/`; CI run 45733617970 |
| Native dataset schema, validator and CLI | Verified (L1, 2026-11-26) | `evidence/20261126_m1/`; 65 tests at M1 acceptance (68 current, including M2 harness) |
| Public LeRobot v3 import and export | Verified (L1, 2026-11-26) | pusht 206 eps/25,650 frames; SO-101 50 eps/11,939 frames; exact tabular round-trip |
| Deterministic synthetic conversion | Verified (L1, 2026-11-26) | identical `root_sha256`; image pixel diff 0 |
| 17-case anomaly detection | Verified (L1, 2026-11-26) | `evidence/20261126_m1/anomaly-matrix.json` |
| Offline training and evaluation | Unverified | Not implemented (M2) |
| Policy inference intent | Unverified | Not implemented (M3) |
| Hardware behavior | Unverified | No L5 session; M1/M2 never touch a robot |
| M2.0 rehearsal harness (not a policy) | Verified (L1, 2026-11-26) | `evidence/20261126_m2-rehearsal/`; `evidence/20261126_m2-mve0/` |
| M2 multi-seed stability + suite proposal | Verified (L1, 2026-11-26) | `evidence/20261126_m2-sweep/`; `docs/m2/BENCHMARK-PROPOSAL.md` |

Full report: [ACCEPTANCE.md](ACCEPTANCE.md).

## Related repositories

- [`jcheng-interfaces`](https://github.com/JCHENG-Robotics/jcheng-interfaces) — contract source and hash.
- [`jcheng-system`](https://github.com/JCHENG-Robotics/jcheng-system) — privileged runtime; sole owner of motion and hardware access.
- [`jcheng-perception`](https://github.com/JCHENG-Robotics/jcheng-perception) — advisory perception targets consumed from M3.
- [`jcheng-simulation`](https://github.com/JCHENG-Robotics/jcheng-simulation) — simulation plant and robot catalog reference.
- [`jcheng-teleop`](https://github.com/JCHENG-Robotics/jcheng-teleop) — future episode producer.
- [`jcheng-benchmark`](https://github.com/JCHENG-Robotics/jcheng-benchmark) — independent evaluation from M2.
- [`jcheng-ops`](https://github.com/JCHENG-Robotics/jcheng-ops) — unattended health and watchdogs.
- [`.github`](https://github.com/JCHENG-Robotics/.github) — ecosystem roadmap, changelog, acceptance and the repository taxonomy.

## License

Pending third-party and copyright review; no `LICENSE` file has been added.
Datasets and model artifacts carry their own licenses and are never covered by
this repository's eventual license. See [LICENSE-REVIEW.md](LICENSE-REVIEW.md).
