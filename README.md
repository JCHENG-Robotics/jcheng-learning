# jcheng-learning

[简体中文](README.zh-CN.md) | **English**

> Status: **Experimental** as of 2026-11-26. Version 0.1.0.
> Offline-first scaffold: the repository defines the dataset, training and
> policy-artifact boundaries, but contains no runtime node, no policy and no
> hardware access. Nothing in it is used by the running robot.
> English canonical; see [README.zh-CN.md](README.zh-CN.md) for the Chinese translation.

`jcheng-learning` is the L3 learning capability of the JCHENG ecosystem. Its
charter is to turn recorded robot episodes into versioned datasets, train and
evaluate policies offline, and — only from M3 — publish skill **intent** for the
system layer to validate and execute. It never drives a device, never rebuilds
motion itself and never bypasses `jcheng-system`.

## Scope and boundary

| Item | This repository |
|---|---|
| Layer | L3 capability (`capability.yaml`) |
| Inputs | Recorded episodes and dataset manifests, both stored outside this repository |
| Outputs | Dataset manifests and model artifacts, both stored outside this repository; from M3, skill intent |
| Motion authority | None in v0.1.0 (`safety.class: offline`, empty runtime surface) |
| Hardware access | `none` |
| Owned devices | none |
| Forbidden | device access, vendor topics, `/cmd_vel`, `/move_action`, `ExecuteMotion`, fabricated sensor data, datasets or model weights in git |

The system layer is the only origin of motion. The perception layer is the only
source of advisory targets. A policy produced here may propose an action; the
system layer applies the control lease, deadman, limits and the stop latch
before anything moves.

## Repository layout

```text
jcheng-learning/
├── capability.yaml                 # admission manifest (offline, hardware_access: none)
├── docs/
│   ├── ARCHITECTURE.md             # data, training and inference planes
│   ├── DATA.md                     # dataset layout, provenance and integrity rules
│   └── INTEGRATION.md              # admission, lease and failure semantics
├── tests/
│   ├── test_contract.py            # manifest and document-set checks
│   └── test_no_hardware.py         # static no-hardware / no-motion scan
├── scripts/check_repo_gate.sh      # repository gate (local and CI)
├── evidence/20261126_scaffold/     # M0 evidence record
├── VERSION
├── README.md / README.zh-CN.md
├── ROADMAP.md / CHANGELOG.md / ACCEPTANCE.md
└── LICENSE-REVIEW.md
```

## Requirements

- Python 3.10 or newer (CI uses 3.12), `pytest` 8.3.4 and `PyYAML` 6.0.2.
- No ROS installation for v0.1.0. ROS 2 Humble is required only from M3, when
  an inference node exists.
- Operator-side storage for datasets and model artifacts, outside this
  repository. Weight files belong in `/opt/jcheng/models/`; recordings and
  datasets never enter git.
- Training hardware (operator laptop GPU) is not part of the repository and is
  not required for the gate.

## Quick start

```bash
python3 -m pytest -q tests
bash scripts/check_repo_gate.sh
```

The gate checks the document set, the admission manifest, relative links,
secrets, model weights, recorded data and the two test modules. It touches no
robot and opens no device.

## Validation status

| Claim | Status | Evidence |
|---|---|---|
| Repository gate and unit tests pass | Partially verified (local 2026-11-26; CI pending) | `evidence/20261126_scaffold/` |
| Manifest declares `hardware_access: none` and an empty runtime surface | Verified (L0, 2026-11-26) | `tests/test_contract.py` |
| No hardware, vendor topic or motion call exists in the tree | Verified (L0, 2026-11-26) | `tests/test_no_hardware.py` |
| Dataset, training or inference capability | Unverified | Not implemented (M1–M3) |

Full report: [ACCEPTANCE.md](ACCEPTANCE.md).

## Related repositories

- [`jcheng-interfaces`](https://github.com/JCHENG-Robotics/jcheng-interfaces) — contract source and hash.
- [`jcheng-system`](https://github.com/JCHENG-Robotics/jcheng-system) — privileged runtime; sole owner of motion and hardware access.
- [`jcheng-perception`](https://github.com/JCHENG-Robotics/jcheng-perception) — advisory perception targets consumed from M3.
- [`jcheng-ops`](https://github.com/JCHENG-Robotics/jcheng-ops) — unattended health and watchdogs.
- [`.github`](https://github.com/JCHENG-Robotics/.github) — ecosystem roadmap, changelog, acceptance and the repository taxonomy.

## License

Pending third-party and copyright review; no `LICENSE` file has been added.
Datasets and model artifacts carry their own licenses and are never covered by
this repository's eventual license. See [LICENSE-REVIEW.md](LICENSE-REVIEW.md).
