# M0 evidence — repository scaffold

> Status: **in progress** as of 2026-11-26.
> Scope: the document set, admission manifest, repository gate and CI for
> `jcheng-learning` v0.1.0. No runtime node, no dataset, no training run, no
> policy and no hardware session.

## 1. Environment

| Item | Value |
|---|---|
| Host | operator laptop, Ubuntu, Python 3.12, pytest 7.4.4 |
| Repository | `JCHENG-Robotics/jcheng-learning`, `main` |
| Robot | not used |
| Motion | none; no command was sent |

## 2. Commands and results

| Command | Result | Log |
|---|---|---|
| `python3 -m pytest -q tests` | pending | — |
| `bash scripts/check_repo_gate.sh` | pending | — |
| CI `learning-gate` | pending | — |

## 3. Claims supported

- The admission manifest parses, matches `VERSION` and declares
  `hardware_access: none` with an empty runtime surface.
- The static scan finds no hardware, vendor-topic or motion token in code,
  configuration or scripts.
- No model weight or recording is tracked.
- The documentation set required by the organization standard exists and its
  relative links resolve.

## 4. Not covered

- Dataset validation, training, evaluation and inference (M1–M3).
- Any hardware or motion behavior (M4).
- CI success until the first run is recorded above.

## 5. Related

- [Acceptance report](../../ACCEPTANCE.md)
- [Roadmap](../../ROADMAP.md)
- [Architecture](../../docs/ARCHITECTURE.md)
