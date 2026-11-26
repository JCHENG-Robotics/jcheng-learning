# jcheng-learning roadmap

> Status: **v0.1.0** as of 2026-11-26. Offline-first scaffold complete; no
> runtime node and no hardware access.

## Current state

| Item | State | Evidence |
|---|---|---|
| Admission manifest (`capability.yaml`) | Complete (2026-11-26) | `capability.yaml`; `tests/test_contract.py` |
| Repository scaffold, gate and CI | Complete (2026-11-26) | `scripts/check_repo_gate.sh`; CI `learning-gate` passed |
| Dataset manifest and integrity gate | Planned | — |
| Offline training and evaluation harness | Planned | — |
| Policy inference intent node | Planned | — |
| Hardware acceptance | Not started | — |

## Milestones

| Milestone | Scope | State | Exit criterion | Evidence |
|---|---|---|---|---|
| M0 | Repository scaffold and admission manifest | Complete (2026-11-26) | The document set, gate and CI `learning-gate` pass; the manifest claims no runtime surface | `evidence/20261126_scaffold/`; CI run 45733617970 |
| M1 | Dataset manifest and integrity gate | Planned | A recorded episode set is accepted or rejected by a documented, tested checker; no robot access and no data in git | — |
| M2 | Offline training and evaluation | Planned | A reproducible training run on external data with fixed seeds, an evaluation protocol and a hashed model artifact; no hardware | — |
| M3 | Policy inference intent node | Planned | A contract-first intent surface exists in `jcheng-interfaces`; mock integration (L2/L3) proves lease, deadman and fail-closed behavior; no motion | — |
| M4 | Supervised hardware acceptance | Planned | Every motion session is separately authorized; the system layer applies limits and the stop latch; L5 evidence is recorded | — |

## Next

1. **M1 — dataset manifest and integrity gate.** Define the dataset layout and
   manifest fields in `docs/DATA.md`, add the checker and its tests, and prove
   it on an exported episode set stored outside the repository. Prerequisites:
   an operator-selected dataset root and the `jcheng-interfaces` v0.1.0
   contract hash. No robot session is required.
2. **M2 — offline training and evaluation.** Add reproducible training
   configuration, seed control, artifact hashing and an evaluation protocol on
   the operator laptop. Prerequisites: M1 accepted; model storage under
   `/opt/jcheng/models/`.

## Out of scope

- Direct motion commands, `/cmd_vel`, `/move_action` and `ExecuteMotion` calls.
- Device access: cameras, serial, CAN, GPIO and the vendor DDS domains.
- Publishing vendor topics or fabricating sensor data, depth or TF.
- Copying vendor code or vendor model weights into the repository.
- Training on the robot or storing datasets and weights in git.
- Acting as an e-stop or a safety function. The platform has no e-stop, brake
  or self-collision model; the system layer's stop latch is not an e-stop.

## Dependencies

- `jcheng-interfaces` `>=0.1,<0.2`; contract hash
  `sha256:0b8d72ced7f54d444d6851d8b99a51a78e2bed3f687324f51a15f76557f24b42`.
- `jcheng-system` API `>=0.1,<0.2` from M3; the system layer remains the only
  origin of motion.
- External dataset and model storage; `/opt/jcheng/models/` for weights.
- Real-robot work requires separate, explicit operator authorization per
  session and is never triggered by CI or unattended runs.
