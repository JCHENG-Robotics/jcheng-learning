# jcheng-learning roadmap

> Status: **v0.2.0** as of 2026-11-26. M1 offline dataset infrastructure is
> complete and verified at L1. No runtime node, policy or hardware access.

## Current state

| Item | State | Evidence |
|---|---|---|
| Admission manifest (`capability.yaml`) | Complete (2026-11-26) | `capability.yaml`; `tests/test_contract.py` |
| Repository scaffold, gate and CI | Complete (2026-11-26) | `scripts/check_repo_gate.sh`; CI `learning-gate` |
| Dataset schema, native store and profiles | Complete (M1, 2026-11-26) | `src/jcheng_learning/native/`; `docs/m1/04-DATA-CONTRACT.md` |
| Validator, quality report and CLI | Complete (M1, 2026-11-26) | `src/jcheng_learning/validate/`; `evidence/20261126_m1/` |
| LeRobot v3 reader, importer and exporter | Complete (M1, 2026-11-26) | pusht 206 eps/25,650 frames; SO-101 50 eps/11,939 frames; exact tabular round-trip |
| M2.0 rehearsal harness (train/eval/policy card) | Complete (2026-11-26) | `evidence/20261126_m2-rehearsal/` |
| M2 formal training and evaluation | Planned | — |
| Policy inference intent node | Planned (M3) | — |
| Hardware acceptance | Not started (M4) | — |

## Milestones

| Milestone | Scope | State | Exit criterion | Evidence |
|---|---|---|---|---|
| M0 | Repository scaffold and admission manifest | Complete (2026-11-26) | The document set, gate and CI `learning-gate` pass; the manifest claims no runtime surface | `evidence/20261126_scaffold/`; CI run 45733617970 |
| M1 | Offline dataset infrastructure | Complete (2026-11-26) | Schema, adapters, validator, action-space mapping, provenance, offline pipeline and CLI are implemented; synthetic, pusht and SO-101 round-trips are recorded; no robot access | `evidence/20261126_m1/` |
| M2 | Offline training and evaluation | In progress (M2.0 rehearsal) | A reproducible training run on external data with fixed seeds, an evaluation protocol and a hashed model artifact; no hardware | `evidence/20261126_m2-mve0/`; `evidence/20261126_m2-rehearsal/` |
| M3 | Policy inference intent node | Planned | A contract-first intent surface exists in `jcheng-interfaces`; mock integration proves lease, deadman and fail-closed behavior; no motion | — |
| M4 | Supervised hardware acceptance | Planned | Every motion session is separately authorized; the system layer applies limits and the stop latch; L5 evidence is recorded | — |

## M1 scope (delivered)

1. Dataset contract: `jcheng.dataset.v1`, `jcheng.episode.v1`,
   `jcheng.provenance.v1`.
2. Dataset adapter: native reader/writer, LeRobot v3 reader/importer/exporter.
3. Dataset validator: `DQ-*` checks for layout, hashes, timestamps, joint order,
   dimensions, units, gripper conventions, limits, NaN/Inf and images.
4. Action-space mapping: explicit per-dimension rules; no implicit reordering.
5. Provenance: source class, robot profile, calibration, software, hashes and
   transformation history.
6. Offline pipeline: synthetic, public, historical (native) and future teleop
   inputs.
7. CLI: `synth`, `inspect`, `validate`, `stats`, `report`, `import`, `convert`,
   `hash`.

## M2 entry status

| Condition | State | Evidence |
|---|---|---|
| M1 accepted | Complete (2026-11-26) | `ACCEPTANCE.md`; `evidence/20261126_m1/` |
| 6 GB VRAM MVE-0 | Complete (2026-11-26): batch 8 fits, batch 16 OOM | `evidence/20261126_m2-mve0/` |
| M2.0 rehearsal harness | Complete (2026-11-26): 20 steps + offline eval + policy card | `evidence/20261126_m2-rehearsal/` |
| M2 multi-seed stability | Complete (2026-11-26): seeds 0/1/2, fixed eval seed | `evidence/20261126_m2-sweep/` |
| Benchmark suite proposal | Proposed (2026-11-26): draft L1/L4 suites validate with the benchmark loader | `docs/m2/BENCHMARK-PROPOSAL.md` |
| Effective batch 64 on 6 GB | Complete (2026-11-26): batch 8 × accum 8, 20 updates, 3.75 GB | `evidence/20261126_m2-gradaccum/` |
| own-real state-truth decision | Pending operator decision | — |
| Evaluation protocol pre-registration | Pending | — |
| Model-artifact and policy-card rules | Pending | — |

## Next

1. **M2 — offline training and evaluation.** Reproducible training configuration,
   seed control, artifact hashing and an evaluation protocol on the operator
   laptop. Start from the measured batch-8 envelope; no hardware.
2. **Decide the training data.** Pick the first accepted dataset (source class,
   `state.truth`, profile) and decide whether own-real recordings are in scope;
   `state.truth=commanded` is degraded and cannot be presented as measured.
3. **Pre-register the evaluation protocol.** Metrics, held-out episodes,
   thresholds and failure semantics before any training run; formal evaluation
   remains in `jcheng-benchmark`.

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
- LeRobot `0.7.0` / dataset `v3.0` for the optional compatibility path; the core
  path does not import torch.
- External dataset and model storage; `/opt/jcheng/models/` for weights.
- Real-robot work requires separate, explicit operator authorization per
  session and is never triggered by CI or unattended runs.
