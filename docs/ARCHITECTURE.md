# Architecture — jcheng-learning

> Status: **Experimental** as of 2026-11-26. Version 0.2.0.
> M1 implements the offline data plane (native store, validator, LeRobot v3
> adapters and CLI). There is still no runtime node, no policy and no device
> access. The training plane is M2 and the inference plane is M3.

## 1. Position in the ecosystem

`jcheng-learning` is an L3 capability. It sits beside `jcheng-mobile`,
`jcheng-perception` and the frozen `jcheng-manipulation` baseline, below the
system layer in the dependency direction:

```text
recorded episodes (external store, read-only)
        │
        ▼
  data plane        dataset manifest + integrity gate        (offline, no ROS)
        │
        ▼
  training plane    reproducible run -> model artifact       (operator laptop GPU)
        │           policy card + SHA-256, stored externally
        ▼
  inference plane   policy node -> skill intent   (M3, domain 42)
        │
        ▼
  jcheng-system     lease, deadman, limits, stop latch, ExecuteMotion
```

Rules that come from the ecosystem and are not negotiable here:

- The system layer is the **only** origin of motion. This repository never
  calls `ExecuteMotion`, never publishes `/cmd_vel` and never writes a servo or
  motor device.
- Capabilities publish **intent**. The system layer decides whether intent
  becomes motion.
- Cross-repository contracts live only in `jcheng-interfaces`. This repository
  does not invent a topic or service that another repository consumes without
  adding the contract there first.
- `hardware_access: none` in `capability.yaml`. No camera, serial, CAN, GPIO or
  vendor DDS domain is opened, now or at M3.
- `/joint_states` from the vendor stack is a **command cache**, not a
  measurement. A dataset that needs pose truth must carry a bus read; a policy
  must never be trained on cached commands as if they were measured positions.

## 2. Data plane (offline)

Capture is not owned here. The system and perception layers own the camera,
depth, TF and status streams; an exporter outside this repository produces the
episode set, and the learning repository consumes it read-only. This keeps the
repository free of device access and keeps recording policy with the layer that
owns the sensors.

M1 implements the data plane as:

1. **Ingest** — `jcheng_learning.synthetic` and
   `jcheng_learning.lerobot.imports` produce the native store; a future
   teleop/simulation exporter can write the same format.
2. **Native store** — `jcheng.dataset.v1` under external storage:
   `dataset.yaml`, `provenance.json`, `SHA256SUMS` and
   `episodes/<id>/{meta.json,frames.jsonl,images/}`.
3. **Validator** — `jcheng_learning.validate` runs the `DQ-*` checks and writes
   `jcheng.dataset-quality-report.v1`; failures are terminal and never repaired.
4. **Export** — `jcheng_learning.lerobot.export` calls the official
   `LeRobotDataset.create/add_frame/save_episode/finalize`; the repository does
   not write Parquet or MP4 itself.
5. **CLI** — `jcheng-dataset synth|inspect|validate|stats|report|import|convert|hash`.

The native format is the audit/provenance record. LeRobot v3 is the training
interchange format; training reads LeRobot, never the native files.

The layout, manifest fields and integrity rules are specified in
[DATA.md](DATA.md). They are **proposed** until M1 accepts them. No dataset is
stored in git, and no dataset is silently repaired: a failed dataset stays
rejected and is re-exported under a new identifier.

## 3. Training plane (offline)

Training runs on the operator laptop GPU, not on the robot. The repository
holds configuration, code and tests; it does not hold data or weights.

| Item | Location | Rule |
|---|---|---|
| Training configuration | this repository | reviewed, seeded, no absolute operator paths |
| Dataset | external store | referenced by `dataset_id` and content hash |
| Training run logs | external store or `evidence/` (summary only) | no full recordings in git |
| Model artifact | `/opt/jcheng/models/` | `*.pt`, `*.onnx`, `*.engine` never in git |
| Policy card | this repository, M2 onward | input contract, training data hash, eval results, limitations |

A training run is reproducible when the dataset hash, configuration hash, code
commit, seed and dependency set are recorded. Evaluation is defined before a
model is promoted; a metric that was not in the protocol is reported as
exploratory, not as acceptance.

## 4. Inference plane (M3, planned)

The inference node will be a thin ROS 2 Humble wrapper around a ROS-free core.
It will:

- subscribe to observation streams owned by perception and the system layer;
- load a model artifact by hash from `/opt/jcheng/models/`;
- publish skill **intent** on domain 42 for the system layer;
- hold no lease of its own and command no motion.

Topic and service names are **not** claimed in v0.1.0. They enter
`jcheng-interfaces` first, then `capability.yaml` and this document change in
the same PR. The manifest then moves from `safety.class: offline` to
`motion_source` with explicit scopes, a bounded rate and a deadman.

## 5. Invariants

| Invariant | Enforcement |
|---|---|
| No hardware access | `capability.yaml`; `tests/test_no_hardware.py` |
| No motion command or motion service call | static scan; review of the M3 contract |
| No fabricated sensor data, depth or TF | review; the data plane records provenance |
| No model weights or recordings in git | `scripts/check_repo_gate.sh`; `.gitignore` |
| Core path has no torch, ROS, GPU or network | `pyproject.toml`; core CI; tests |
| No vendor code copied | review; differences are recorded as documents |
| Fail closed | no intent on stale input, missing lease, hash mismatch or load failure |
| One RMW per graph, domain 42 only at M3 | deployment review; the repository ships no DDS configuration |
| No secrets in the tree | gate secret scan; operator storage only |

## 6. Failure semantics

| Condition | Required behavior |
|---|---|
| Observation stream stale | emit no new intent; the system's deadman stops motion |
| No valid lease | emit nothing; the system rejects intent without a lease |
| Model hash mismatch or load failure | refuse to start; do not fall back to another model |
| Dataset integrity failure | reject the dataset; no partial training |
| Clock or timestamp inconsistency | reject the episode at the gate; do not rebase silently |
| Out-of-distribution input | no safety claim; the system's limits and operator remain responsible |

An uncertainty estimate or an OOD score is **not** a safety function. The
platform has no e-stop, brake, encoder or self-collision model; the system
layer's stop latch is a software stop, not an e-stop.

## 7. Non-goals

- Recording from devices, owning cameras, or joining the vendor DDS domain.
- Training on the robot, or shipping a training stack into the robot image.
- Replacing perception, motion planning or the system layer's safety policy.
- Any claim of hardware validation without a separate, supervised L5 session.
