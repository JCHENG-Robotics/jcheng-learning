# Integration — jcheng-learning

> Status: **Experimental** as of 2026-11-26. v0.1.0 has no runtime surface:
> no node is started, no topic is published and no lease is acquired.
> The M3 contract below is planned, not implemented.

## 1. Discovery and admission

The system reads `capability.yaml` and checks the admission fields. For
v0.1.0 it finds:

| Field | Value | Meaning |
|---|---|---|
| `name` | `jcheng-learning` | capability identity |
| `version` | `0.1.0` | must match `VERSION` |
| `contract.interfaces` | `>=0.1,<0.2` | pinned contract range |
| `contract.contract_hash` | `sha256:0b8d72…24b42` | must match the interfaces manifest |
| `safety.class` | `offline` | no intent source yet |
| `safety.scopes` | `[]` | no motion scope |
| `safety.requires_lease` | `true` | required by the schema; vacuous while there is no runtime |
| `hardware_access` | `none` | hard boundary |
| `runtime` | empty | no domain, no topics |

Because the runtime surface is empty, admission means "no runtime object to
discover". A future M3 adds the node, the topics and a contract change in the
same PR. Until then, the system must not assume a learning node exists.

## 2. Inputs owned by other layers

| Input | Owner | Used at | Note |
|---|---|---|---|
| Recorded episodes | system/perception capture | M1 | exported files; no device access here |
| Camera, depth, TF streams | perception | M3 | advisory only; never reconstructed |
| Robot and safety state | system | M3 | read-only context for intent generation |

## 3. Planned M3 intent surface

The inference node will publish **skill intent**, not motion. The exact topic
and message type do not exist in `jcheng-interfaces` v0.1.0 and are therefore
not claimed here.

Contract-first checklist for M3:

1. Add the skill-intent message and any observation agreement to
   `jcheng-interfaces`; regenerate the manifest and bump the contract.
2. Update `capability.yaml` to `safety.class: motion_source` with explicit
   scopes, `max_rate_hz` and `deadman_ms`, and a non-empty `runtime`.
3. Update this document and `docs/ARCHITECTURE.md` in the same PR.
4. Prove the mock path (L2/L3): intent is rejected without a lease, dropped on
   stale input, and clamped by the system layer.
5. Only then request a supervised hardware session (L5), separately authorized.

What the system layer must do with learning intent:

- treat it as a proposal, never as a trajectory or a servo command;
- apply the control lease, deadman, joint/base limits and the stop latch;
- reject intent produced from stale or invalid observations;
- log the model artifact hash that produced the intent;
- never treat a policy output as a measurement or as a safety guarantee.

## 4. Lease and failure semantics (M3)

- No valid lease for the declared scope: emit no intent.
- Observation stream older than the agreed bound: emit no intent; the system's
  deadman stops motion.
- Model artifact hash mismatch, missing artifact or load failure: refuse to
  start; no fallback model.
- Internal error or exception: fail closed and stop publishing.
- Missing calibration or invalid TF: no intent that depends on them.
- The node never calls `ExecuteMotion`, never publishes `/cmd_vel` and never
  writes a device.

## 5. Security and operations

- No network listener, no gateway token and no SSH material in this
  repository or its runtime node.
- Model artifacts are read from `/opt/jcheng/models/` by hash; the node does
  not download them at runtime.
- The node joins only domain 42 at M3, with the system's RMW. It ships no DDS
  configuration of its own.
- Startup, restart and stop are the system layer's decision; this repository
  provides no systemd unit for the robot.

## 6. Verification

| Stage | Evidence |
|---|---|
| v0.1.0 admission | `python3 -m pytest -q tests`; `bash scripts/check_repo_gate.sh` |
| M1 dataset gate | validator tests plus accepted/rejected dataset records |
| M2 training | reproducible run record and hashed artifact |
| M3 mock integration | rejection, stale-input and deadman scenarios |
| M4 hardware | separately authorized L5 session with system limits active |

No hardware claim is valid before M4. Synthetic or mock results are never
reported as hardware validation.
