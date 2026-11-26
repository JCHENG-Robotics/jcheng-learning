# M0 evidence — repository scaffold

> Status: **complete** as of 2026-11-26.
> Scope: the document set, admission manifest, repository gate and CI for
> `jcheng-learning` v0.1.0. No runtime node, no dataset, no training run, no
> policy and no hardware session.

## 1. Environment

| Item | Value |
|---|---|
| Repository | `JCHENG-Robotics/jcheng-learning` (public, created 2026-11-26T01:07:30Z) |
| Initial commit | `1e70062` (`chore: initialize jcheng-learning repository`) |
| Operator host | operator laptop, Linux x86_64, Python 3.12.3, pytest 7.4.4 |
| CI host | `ubuntu-latest`, Python 3.12, pytest 8.3.4, PyYAML 6.0.2 |
| Robot | not used |
| Motion | none; no command was sent |

## 2. Commands and results

| Command | Result | Log |
|---|---|---|
| `python3 -m pytest -q tests` | pass, 13 tests | `gate.txt` |
| `bash scripts/check_repo_gate.sh` | pass | `gate.txt` |
| Manifest schema validation against `capability-manifest.v1.schema.json` | pass | `gate.txt` header; `tests/test_contract.py` |
| CI `learning-gate` on `1e70062` | pass ([run 45733617970](https://github.com/JCHENG-Robotics/jcheng-learning/actions/runs/45733617970)) | [`job learning-gate`](https://github.com/JCHENG-Robotics/jcheng-learning/actions/runs/45733617970/job/139621440222) |

## 3. Claims supported

- The admission manifest parses, matches `VERSION`, validates against the v1
  schema and declares `hardware_access: none` with an empty runtime surface.
- The static scan finds no hardware, vendor-topic or motion token in code,
  configuration or scripts.
- No model weight or recording is tracked.
- The documentation set required by the organization standard exists and its
  relative links resolve.
- The same gate passes in CI on `main`.

## 4. Not covered

- Dataset validation, training, evaluation and inference (M1–M3).
- Any hardware or motion behavior (M4).
- Reviewer sign-off; the operator is the only account.

## 5. Related

- [Acceptance report](../../ACCEPTANCE.md)
- [Roadmap](../../ROADMAP.md)
- [Architecture](../../docs/ARCHITECTURE.md)
