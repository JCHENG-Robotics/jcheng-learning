# 04 — 数据契约与跨仓库接口边界

> 状态：**M1 冻结**（2026-11-26，v0.2.0）。规范性文件；实现按此执行。
> 实施偏差见 [03-DESIGN.md](03-DESIGN.md) §12。
> 版本：`jcheng.dataset.v1`（本轮提案，冻结后不可原地修改）。
> 上游事实：LeRobot v3.0 的字段与限制见
> [02-LEROBOT-RESEARCH.md](02-LEROBOT-RESEARCH.md)。

## 1. 契约分层

| 契约 | 文件 | 作用 | 是否跨仓库 |
|---|---|---|---|
| `jcheng.dataset.v1` | `dataset.yaml` | 数据集清单、动作空间、时间、完整性 | M1 否 |
| `jcheng.episode.v1` | `episodes/<id>/meta.json` + `frames.jsonl` | 单 episode 的帧级观测/动作 | M1 否 |
| `jcheng.provenance.v1` | `provenance.json` | 来源、软件、标定、转换历史 | M1 否 |
| `jcheng.learning.robot-adapter.v1` | `robot-adapter.yaml` | 机器人学习侧 profile | M1 否 |
| `jcheng.action-map.v1` | `action-map.yaml` | 显式动作空间映射 | M1 否 |
| `jcheng.dataset-quality-report.v1` | 报告 JSON | 校验结果与统计 | M1 否 |
| LeRobot Dataset v3.0 | `meta/` + `data/` + `videos/` | 训练交换格式 | 上游契约 |

M1 不修改 `jcheng-interfaces`。任何其他仓库要写这些文件，必须先提案到
interfaces（见 §15）。

## 2. 目录布局

```text
<dataset-root>/
└── <dataset_id>/                       # 不可变；只读
    ├── dataset.yaml                    # 本文件 §3
    ├── provenance.json                 # §7
    ├── SHA256SUMS                      # §2.2
    └── episodes/
        └── <episode_id>/
            ├── meta.json               # §4
            ├── frames.jsonl            # §5
            ├── images/
            │   └── <camera_key>/
            │       └── <frame_index:06d>.png
            ├── measurements.jsonl      # 可选，§6.1
            └── labels.jsonl            # 可选，§6.2
```

### 2.1 不可变规则

1. 数据集目录一旦发布，任何文件不得修改；修正 = 新 `dataset_id`。
2. `dataset_id` 只能包含 `[a-z0-9._-]`，长度 ≤ 96，且全局唯一。
3. 不允许符号链接、硬链接、绝对路径、`..` 路径段。
4. 不允许在数据集根下出现未在 `SHA256SUMS` 中列出的常规文件。
5. 数据集不得位于 git 工作树内；`jcheng-learning` 只保存规范与证据。

### 2.2 `SHA256SUMS`

- 每行：`<64 位小写 hex>  <相对路径>`，路径使用 `/`，按路径字节序排序。
- 覆盖：**除 `SHA256SUMS` 自身以外**的全部文件（含 `dataset.yaml`、
  `provenance.json`、`episodes/**`）。
- 数据集内部不保存 `SHA256SUMS` 的哈希或包含自身的总字节数，避免自引用/
  不动点；`root_sha256 = SHA256(SHA256SUMS)` 记录在质量报告与验收证据中。
- 末尾单个 LF；UTF-8；不接受空行/注释。

## 3. `dataset.yaml`

### 3.1 示例（ArmPi 合成集）

```yaml
schema: jcheng.dataset.v1
dataset_id: synthetic-armpi_ultra-20261126T000000Z-000001
created_at: "2026-11-26T00:00:00+08:00"
source_class: synthetic

robot:
  adapter_id: armpi_ultra
  adapter_version: "1.0.0"
  adapter_sha256: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  dof: 5
  has_gripper: true

state:
  space_id: armpi_ultra.joint_state.v1
  names: [joint1, joint2, joint3, joint4, joint5, r_joint]
  units: [rad, rad, rad, rad, rad, rad]
  truth: measured
  truth_source: generator_truth
  si_conformant: true

action:
  space_id: armpi_ultra.joint_position_absolute.v1
  kind: joint_position_absolute
  names: [joint1, joint2, joint3, joint4, joint5, r_joint]
  units: [rad, rad, rad, rad, rad, rad]
  si_conformant: true
  gripper:
    name: r_joint
    space: canonical          # canonical | raw_joint | normalized
    closed: 0.0
    open: 2.22

timing:
  nominal_fps: 10
  clock_source: monotonic     # monotonic | ros_time | system | lerobot
  time_unit: ns
  max_frame_jitter_ms: 10
  max_camera_skew_ms: 50

streams:
  - {id: state, kind: joint_state, rate_hz: 10, required: true}
  - {id: camera.external, kind: image, rate_hz: 8, required: true, camera_key: external}
  - {id: camera.wrist, kind: image, rate_hz: 12, required: false, camera_key: wrist}

cameras:
  - key: external
    width: 640
    height: 480
    encoding: rgb8
    frame_id: camera_color_optical_frame
    calibration_id: calib_d435i_20261124
  - key: wrist
    width: 640
    height: 400
    encoding: rgb8
    frame_id: camera_optical_measured
    calibration_id: calib_wrist_handeye_20261118

episodes:
  - {id: ep_0001, frames: 40, duration_s: 4.0, task: "pick the cube", outcome: success}
  - {id: ep_0002, frames: 40, duration_s: 4.0, task: "pick the cube", outcome: failure}
tasks: ["pick the cube"]

```

### 3.2 字段表

| 字段 | 必填 | 类型 | 规则 |
|---|---|---|---|
| `schema` | 是 | string | 固定 `jcheng.dataset.v1` |
| `dataset_id` | 是 | string | `[a-z0-9._-]{1,96}`；唯一 |
| `created_at` | 是 | string | ISO 8601 带时区 |
| `source_class` | 是 | enum | `synthetic / simulation / public-real / own-real` |
| `robot.adapter_id` | 是 | string | 必须存在于 profile registry |
| `robot.adapter_version` | 是 | string | SemVer |
| `robot.adapter_sha256` | 是 | string | profile 规范化字节的 SHA-256 |
| `robot.dof` | 是 | int | ≥1；与 profile 一致 |
| `robot.has_gripper` | 是 | bool | 与 profile 一致 |
| `state.space_id` | 是 | string | `<profile>.joint_state.v<n>` |
| `state.names` | 是 | list[str] | 有序；与 profile 完全一致 |
| `state.units` | 是 | list[str] | 每维一个；见 §3.3 |
| `state.truth` | 是 | enum | `measured / commanded / unknown`；`mixed` 不允许 |
| `state.truth_source` | 是 | enum | `bus_read / simulator_truth / generator_truth / command_cache / source_dataset / unknown` |
| `state.si_conformant` | 是 | bool | own/sim/synth 必须 true |
| `action.space_id` | 是 | string | `<profile>.joint_position_absolute.v<n>` |
| `action.kind` | 是 | enum | M1 仅 `joint_position_absolute` |
| `action.names` / `units` | 是 | list | 有序；每维一个 |
| `action.si_conformant` | 是 | bool | own/sim/synth 必须 true |
| `action.gripper` | 条件 | object | 有夹爪时必填 |
| `timing.nominal_fps` | 是 | int | ≥1；LeRobot 导出要求整数 |
| `timing.clock_source` | 是 | enum | 见 §5.3 |
| `timing.time_unit` | 是 | string | M1 固定 `ns` |
| `timing.max_frame_jitter_ms` | 是 | number | ≥0 |
| `timing.max_camera_skew_ms` | 是 | number | ≥0 |
| `streams[]` | 是 | list | 至少一个 state 流 |
| `cameras[]` | 条件 | list | 有 image 流时必填 |
| `episodes[]` | 是 | list | 非空；id 唯一 |
| `tasks` | 是 | list[str] | 非空；包含所有 episode 的 task |
| `export_hints` | 否 | object | 不作为事实源 |

### 3.3 单位词表

| 单位 | 允许用于 | 说明 |
|---|---|---|
| `rad` | revolute 关节、角度 | SI |
| `rad_s` | 速度 | SI |
| `m` | prismatic 关节、位移 | SI |
| `m_s` | 线速度 | SI |
| `normalized` | 夹爪/归一化量 | 必须给出 `[closed, open]` 或 `[min,max]` |
| `deg` | **仅 public-real 导入** | 必须 `si_conformant: false` |
| `px` | **仅 `simulation` 且 `origin.public: true` 的导入** | 必须 `si_conformant: false` |
| `pulse` | **仅诊断数据** | 不得进入训练导出 |

规则：

- `own-real`、`simulation`、`synthetic` 的 state/action 必须 SI
  （`rad`/`m`/`normalized`）；`deg`/`px` 仅用于导入的公开数据集。
- 每维单位独立声明；允许混合（例如 5 个 `deg` + 1 个 `normalized`），
  但 `si_conformant` 必须为 false 并写入 `provenance.transformations`。
- 单位字符串区分大小写；`rad` ≠ `radian`，不做模糊匹配。

## 4. `episodes/<id>/meta.json`

```json
{
  "schema": "jcheng.episode.v1",
  "episode_id": "ep_0001",
  "start_ns": 1720000000000000000,
  "end_ns": 1720000004000000000,
  "nominal_fps": 10,
  "task": "pick the cube",
  "outcome": "success",
  "operator_session_id": null,
  "capture": {
    "method": "generator",
    "tool": "jcheng-dataset",
    "version": "0.2.0"
  },
  "frames": 40,
  "labels": []
}
```

| 字段 | 必填 | 规则 |
|---|---|---|
| `schema` | 是 | `jcheng.episode.v1` |
| `episode_id` | 是 | `[a-z0-9._-]{1,64}`；数据集内唯一 |
| `start_ns` / `end_ns` | 是 | 会话单调时钟 ns；`end > start` |
| `nominal_fps` | 是 | 与 manifest 一致 |
| `task` | 是 | 非空；必须在 manifest `tasks` 中 |
| `outcome` | 是 | `success / failure / unknown / aborted` |
| `operator_session_id` | 条件 | own-real 必填；public 为 `null` |
| `capture.method` | 是 | `generator / import / recording / simulation` |
| `frames` | 是 | 与 `frames.jsonl` 行数一致 |
| `labels` | 否 | 阶段标签数组；不参与 M1 导出 |

## 5. `frames.jsonl`

每行一个 JSON 对象，UTF-8，无 BOM，末尾 LF；行号 = `frame_index + 1`
（出现空行即错误）。

### 5.1 示例

```json
{"frame_index":0,"t_ns":1720000000000000000,"observation":{"state":[0.0,0.0,0.0,0.0,0.0,0.0],"truth":"measured","images":{"external":{"path":"images/external/000000.png","stamp_ns":1719999999950000000,"width":640,"height":480,"encoding":"rgb8"}}},"action":{"kind":"joint_position_absolute","space_id":"armpi_ultra.joint_position_absolute.v1","values":[0.01,0.0,0.0,0.0,0.0,0.0]},"valid":true,"flags":[]}
```

### 5.2 字段

| 字段 | 必填 | 规则 |
|---|---|---|
| `frame_index` | 是 | int；从 0 连续 |
| `t_ns` | 是 | int；会话单调 ns；非递减 |
| `observation.state` | 是 | float 数组；长度 = `state.names` |
| `observation.truth` | 是 | `measured / commanded / unknown`；不得与 manifest 冲突 |
| `observation.images` | 条件 | 每个 `cameras[].key` 一项；见 §5.4 |
| `action.kind` | 是 | 与 manifest 一致 |
| `action.space_id` | 是 | 与 manifest 一致 |
| `action.values` | 是 | float 数组；长度 = `action.names` |
| `valid` | 是 | bool；false 的帧不得导出 |
| `flags` | 否 | 字符串数组；诊断用，不改变语义 |
| `task` | 否 | 若出现，必须在 manifest `tasks` 中 |

### 5.3 时间语义

- `t_ns` 是**会话单调时钟**，不是 Unix epoch；墙钟只在
  `dataset.yaml.created_at` / `provenance.capture.started_at` 出现。
- `clock_source`：
  - `monotonic`：`CLOCK_MONOTONIC` 或等价；
  - `ros_time`：ROS 时间（必须确认未被仿真时钟污染）；
  - `system`：系统墙钟（only if monotonic unavailable；必须记录 NTP 状态）；
  - `lerobot`：来自 LeRobot `timestamp`（秒浮点），导入时换算为 ns。
- 不允许同一数据集混用时钟源。
- `timestamp` 浮点秒仅存在于 LeRobot 导出层；原生层禁止浮点秒。

### 5.4 图像条目

| 字段 | 必填 | 规则 |
|---|---|---|
| `path` | 是 | 相对 episode 目录；必须匹配 `images/<camera>/<frame:06d>.png` |
| `stamp_ns` | 是 | int；采集时刻（同会话时钟） |
| `width` / `height` | 是 | int；与 manifest 相机声明一致 |
| `encoding` | 是 | M1 仅 `rgb8` |
| `frame_id` | 否 | 覆盖 manifest 的 frame_id |
| `calibration_id` | 否 | 覆盖 manifest 的标定 ID |

- `|stamp_ns - t_ns| ≤ max_camera_skew_ms × 1e6`，否则 DQ-T06 error。
- 文件必须是 8-bit RGB PNG；不允许 JPEG、16-bit、RGBA、灰度。
- 缺失 `required: true` 的相机 = 缺帧，DQ-I01 error。
- 可选相机缺失时，`valid` 仍可为 true，但 `flags` 记 `camera_missing:<key>`。

## 6. 可选日志

### 6.1 `measurements.jsonl`

总线实测，独立于 `observation.state`：

```json
{"t_ns":1720000000050000000,"source":"GetBusServoState","positions_rad":[...],"pulses":[...],"latency_ms":12.3}
```

规则：

- 不得与 `observation.state` 混写。
- `truth_source=bus_read` 时，必须有至少一条覆盖 episode 时段的
  measurement（否则 DQ-P02 error）；`truth_source=simulator_truth` /
  `generator_truth` / `command_cache` / `source_dataset` 时，measurements
  可选。
- `pulses` 只作诊断；训练导出不使用。
- 无安全超时的总线读不得在 M1 实现；M1 只消费离线文件。

### 6.2 `labels.jsonl`

```json
{"t_ns":1720000001000000000,"phase":"approach","label":"pre_grasp","source":"operator"}
```

阶段标签用于 M2 评估，不参与 M1 导出；不得由待评估策略推断。

## 7. `provenance.json`

### 7.1 示例

```json
{
  "schema": "jcheng.provenance.v1",
  "dataset_id": "synthetic-armpi_ultra-20261126T000000Z-000001",
  "source_class": "synthetic",
  "origin": {
    "kind": "generator",
    "public": false,
    "generator": {"name": "jcheng-dataset", "version": "0.2.0", "seed": 0,
                   "config_sha256": "sha256:2222..."}
  },
  "robot": {"adapter_id": "armpi_ultra", "adapter_sha256": "sha256:0000..."},
  "software": {
    "jcheng_learning": "0.2.0",
    "git_commit": "0000000",
    "contract_hash": "sha256:0b8d72ced7f54d444d6851d8b99a51a78e2bed3f687324f51a15f76557f24b42",
    "python": "3.12.3",
    "lock_sha256": "sha256:3333..."
  },
  "capture": {
    "method": "generator",
    "operator_session_id": null,
    "authorization_ref": null,
    "started_at": "2026-11-26T00:00:00+08:00",
    "ended_at": "2026-11-26T00:00:04+08:00"
  },
  "calibration": [
    {"id": "calib_d435i_20261124", "kind": "intrinsics", "sha256": "sha256:4444..."}
  ],
  "license": {"dataset": "internal", "consent": null, "redistribution": "none"},
  "upstream": null,
  "transformations": []
}
```

### 7.2 来源类别规则

| `source_class` | 必填额外字段 | 禁止 |
|---|---|---|
| `synthetic` | `origin.generator.name/version/seed/config_sha256` | 声称硬件/真机 |
| `simulation` | `origin.simulator`（repo/version/profile_hash/truth_topic） | 声称硬件 |
| `public-real` | `upstream.repo_id/revision/license/files[]`；`license.dataset` 为 SPDX | 声称 JCHENG 采集 |
| `own-real` | `capture.operator_session_id`、`capture.authorization_ref`、`calibration[]`、`license.consent`（如有人像） | 无授权引用 |

- `public-real` 的 `origin.public` 必须为 true；`simulation` 可以是 public
  或 internal，用 `origin.public` 区分。
- `truth_source` 必须与 `source_class` 匹配：`synthetic → generator_truth`、
  `simulation → simulator_truth|source_dataset`（public 导入用后者）、
  `own-real → bus_read|command_cache`、
  `public-real → source_dataset|unknown`；不匹配 = error（DQ-P07）。
- `truth: unknown` 只允许出现在 `public-real` 导入；own-real/sim/synth 必须
  明确 `measured` 或 `commanded`。
- 与 `jcheng-system` 的 `RobotState` 对齐：`truth=measured` + `verification=bus`
  → `truth_source=bus_read`；`truth=commanded` → `command_cache`；
  `truth=measured` 但 `verification!=bus`（`timed`/`open_loop`）视为不一致，
  拒绝导入，不得把定时插值当测量。
- `mix` 不允许：一个数据集只能一个 `source_class`；混合来源 = 多个数据集。
- `transformations[]` 只记录**产生本数据集**的输入；输出哈希写质量报告，
  避免自引用。每条含 `tool/version/at/operation/input{dataset_id,root_sha256}
  /params/params_sha256`。

### 7.3 软件与契约

- `software.contract_hash` 必填，即使 M1 不使用运行时契约；它锚定采集时的
  `jcheng-interfaces` 版本。
- `software.lock_sha256` 是 `uv.lock` 的 SHA-256；无锁构建不得声称可复现。
- `git_commit` 必须是产生数据集的仓库提交；dirty 工作树必须记
  `git_dirty: true`。

## 8. `robot-adapter.yaml`

### 8.1 示例（ArmPi Ultra）

```yaml
schema: jcheng.learning.robot_adapter.v1
id: armpi_ultra
version: "1.0.0"
display_name: ArmPi Ultra

refs:
  simulation:
    path: jcheng-simulation/ros2_ws/src/jcheng_simulation_robots/robots/armpi_ultra/robot.yaml
    sha256: "sha256:6666..."
  system:
    path: "operator-provided deployment profile (outside this repository)"
    sha256: "sha256:7777..."

dof: 5
joints:
  - {name: joint1, index: 0, type: revolute, unit: rad, lower: -1.8012, upper: 1.8012, role: shoulder_pan}
  - {name: joint2, index: 1, type: revolute, unit: rad, lower: -0.6618, upper: 1.1519, role: shoulder_lift}
  - {name: joint3, index: 2, type: revolute, unit: rad, lower: -1.8012, upper: 0.0,    role: elbow}
  - {name: joint4, index: 3, type: revolute, unit: rad, lower: -1.5917, upper: 1.5917, role: wrist_pitch}
  - {name: joint5, index: 4, type: revolute, unit: rad, lower: -1.5917, upper: 1.5499, role: wrist_roll}

gripper:
  name: r_joint
  index: 5
  type: revolute
  unit: rad
  space: canonical
  closed: 0.0
  open: 2.22
  raw_space:
    name: r_joint
    lower: -2.22
    upper: 0.0
    direction: increasing_closes
  max_velocity_rad_s: 1.0

state_spaces:
  - id: armpi_ultra.joint_state.v1
    names: [joint1, joint2, joint3, joint4, joint5, r_joint]
    units: [rad, rad, rad, rad, rad, rad]
    gripper: {name: r_joint, space: canonical}
    truth_allowed: [measured, commanded]
  - id: armpi_ultra.raw_joint_state.v1
    names: [joint1, joint2, joint3, joint4, joint5, r_joint]
    units: [rad, rad, rad, rad, rad, rad]
    gripper: {name: r_joint, space: raw_joint}
    truth_allowed: [commanded]

action_spaces:
  - id: armpi_ultra.joint_position_absolute.v1
    kind: joint_position_absolute
    names: [joint1, joint2, joint3, joint4, joint5, r_joint]
    units: [rad, rad, rad, rad, rad, rad]
    gripper: {name: r_joint, space: canonical}
    limits_known: true
  - id: armpi_ultra.raw_joint.v1
    kind: joint_position_absolute
    names: [joint1, joint2, joint3, joint4, joint5, r_joint]
    units: [rad, rad, rad, rad, rad, rad]
    gripper: {name: r_joint, space: raw_joint}
    limits_known: true

cameras:
  - {key: external, role: external, required: true, width: 640, height: 480,
     rate_hz: 8, frame_id: camera_color_optical_frame}
  - {key: wrist, role: wrist, required: false, width: 640, height: 400,
     rate_hz: 12, frame_id: camera_optical_measured}

capabilities:
  mobile_base: false
  can_lift: false
  max_payload_kg: null
```

### 8.2 规则

- `id` 全局唯一；`version` 变更必须新建 profile（不允许原地改限位/单位）。
- `refs` 只记录来源路径与哈希；不复制上游文件内容。
- 有夹爪时，`gripper.index` 必须等于动作向量最后一维；`dof` 只数臂关节，
  不含夹爪。
- `dataset.yaml.state.space_id` 必须存在于 profile 的 `state_spaces`；
  `action.space_id` 必须存在于 `action_spaces`。
- `state_spaces[].names` 与 `action_spaces[].names` 的并集必须覆盖
  `dof + gripper`；维度必须与 `names` 长度一致。
- `limits_known: false` 时，校验器跳过限位检查并标 `inconclusive`；不得
  据此声称“限位安全”。
- 相机 `rate_hz` 是标称值，不用于推导数据帧率；实际以数据为准。
- `gripper.space` 的必填字段：
  - `canonical`：`closed` / `open`（ArmPi：0.0 / 2.22 rad）；
  - `raw_joint`：`raw_space.lower` / `upper` / `direction`；
  - `normalized`：`range_known`；为 true 时必须有 `min` / `max`，否则
    限位检查记 `inconclusive`；
  - `linear`：`closed` / `open`，单位 m（Piper X：0.0 / 0.1）。

### 8.3 三个机器人的差异

| 项 | ArmPi Ultra | Gate-2 | Piper X | SO-101（仅导入） |
|---|---|---|---|---|
| 臂关节 | 5 revolute | 2 revolute | 6 revolute | 5 revolute |
| 夹爪 | revolute `r_joint`，canonical 0…2.22 | 无 | prismatic `gripper` 0…0.1 m | revolute `gripper`，归一化 |
| 动作维度 | 6 | 2 | 7 | 6 |
| 单位 | rad | rad | rad / m | deg / normalized |
| 限位来源 | 仿真 catalog + 系统 profile | 仿真 catalog | MIT URDF + 仿真 catalog | 公开数据集未提供 → `limits_known: false` |

维度相同（ArmPi 6 vs SO-101 6）**不构成**动作空间兼容；动作空间 ID 必须
不同，跨机器人必须显式 map + 重训。

SO-101 导入 profile 的关键字段（名称必须与公开数据集 feature `names` 逐位
一致；单位来自实测值域，不是猜测）：

```yaml
id: so101_follower
version: "1.0.0"
dof: 5
state_spaces:
  - id: so101_follower.joint_state.v1
    names: [shoulder_pan.pos, shoulder_lift.pos, elbow_flex.pos,
            wrist_flex.pos, wrist_roll.pos, gripper.pos]
    units: [deg, deg, deg, deg, deg, normalized]
    gripper: {name: gripper.pos, space: normalized, range_known: false}
    truth_allowed: [unknown]
action_spaces:
  - id: so101_follower.joint_position_absolute.v1
    kind: joint_position_absolute
    names: [shoulder_pan.pos, shoulder_lift.pos, elbow_flex.pos,
            wrist_flex.pos, wrist_roll.pos, gripper.pos]
    units: [deg, deg, deg, deg, deg, normalized]
    gripper: {name: gripper.pos, space: normalized, range_known: false}
    limits_known: false
```

## 9. `action-map.yaml`

```yaml
schema: jcheng.action-map.v1
from_space: armpi_ultra.raw_joint.v1
to_space: armpi_ultra.joint_position_absolute.v1
transfer_claim: none          # none | research-only | validated
rules:
  - {to_index: 0, to_name: joint1, from_index: 0, from_name: joint1,
     scale: 1.0, offset: 0.0, unit_in: rad, unit_out: rad}
  - {to_index: 5, to_name: r_joint, from_index: 5, from_name: r_joint,
     scale: -1.0, offset: 0.0, unit_in: rad, unit_out: rad,
     note: "raw r_joint -2.22..0 (increasing closes) -> canonical 0..2.22; offset is 0"}
unmapped: []
```

规则：

1. 每个 `to_index` 恰好一条规则；重复/缺失 → error。
2. `from_index` 可重复（一个源驱动多个目标），但必须在报告中列出。
3. `scale`/`offset` 必须是有限数；`unit_in/unit_out` 必须在单位词表中。
4. 映射后必须重新校验限位/单位；映射链最多 1 跳（M1 不做链式映射）。
5. `transfer_claim: none` 的映射不得用于训练声明；`research-only` 只用于
   实验；`validated` 需要独立证据。
6. 映射写入 `provenance.transformations`，并产生新的 `dataset_id`。

## 10. 质量报告 `jcheng.dataset-quality-report.v1`

```json
{
  "schema": "jcheng.dataset-quality-report.v1",
  "dataset": {
    "id": "synthetic-armpi_ultra-20261126T000000Z-000001",
    "root_sha256": "sha256:8888...",
    "source_class": "synthetic",
    "profile_id": "armpi_ultra",
    "profile_sha256": "sha256:0000..."
  },
  "tool": {"version": "0.2.0", "git_commit": "0000000", "lock_sha256": "sha256:3333..."},
  "run": {"started_at": "2026-11-26T00:10:00+08:00", "duration_s": 1.23, "deterministic": true},
  "summary": {"result": "pass", "usable_for_training": true,
               "errors": 0, "warnings": 0, "skipped": 1, "inconclusive": 0},
  "checks": [
    {"id": "DQ-T04", "severity": "warning", "status": "pass",
     "message": "max jitter 3.2 ms within 10 ms", "counts": {"frames": 120}},
    {"id": "DQ-I09", "severity": "error", "status": "skip",
     "message": "images mode; no video", "counts": {}}
  ],
  "features": {
    "observation.state": {"count": 120, "min": [-1.8, -0.6, -1.8, -1.5, -1.5, 0.0],
                           "max": [1.8, 1.1, 0.0, 1.5, 1.5, 2.22],
                           "mean": [0.0, 0.0, -0.7, 0.0, 0.0, 1.1],
                           "std": [1.0, 0.4, 0.5, 0.8, 0.8, 0.6],
                           "nan": 0, "inf": 0}
  },
  "episodes": [
    {"id": "ep_0001", "frames": 40, "duration_s": 4.0, "dropped_frames": 0,
     "images": {"external": 40, "wrist": 40}}
  ],
  "limitations": ["synthetic; no hardware claim"]
}
```

规则：

- `summary.result` 由检查聚合；`fail > inconclusive > degraded > pass`。
- `checks[]` 按 `id` 排序；每个检查必须有 `status`；`skip` 必须给理由。
- `features` 的统计必须与数据重算一致（DQ-X03）；允许报告只含部分特征。
- `root_sha256 = SHA256(SHA256SUMS 文件字节)`；该文件传递覆盖 manifest、
  provenance 与全部 episode 文件（见 §2.2）。
- 报告不写回数据集目录；不参与 `SHA256SUMS`。

## 11. LeRobot 导出映射与 sidecar

### 11.1 特征映射

| 原生 | LeRobot feature | dtype/shape |
|---|---|---|
| `observation.state` | `observation.state` | `float32`, `[D_state]`, `names` |
| `action.values` | `action` | `float32`, `[D_action]`, `names` |
| `images.<key>` | `observation.images.<key>` | `image` 或 `video`, `[H,W,3]` |
| `task` | 每帧 `task` | string |
| `t_ns` | `timestamp` | 导出网格 `k/fps` |

- `robot_type` = profile `id`。
- `fps` = 导出整数；不得大于任一 `required` 流的标称频率。
- `use_videos` 由 `--mode images|videos` 决定；M1 默认 `images`。
- 不导出 `measurements/labels/depth/detections`。

### 11.2 sidecar

输出根目录（LeRobot 数据集的同级，不进入 `meta/`）：

```text
<export-dir>/
├── meta/ data/ [videos/]          # LeRobot 官方布局；图像模式无 images/
└── jcheng/
    ├── export.json                # 本次导出的参数与源哈希
    ├── provenance.json            # 原生 provenance 的副本
    └── quality.json               # 导出前质量报告
```

`jcheng/export.json`：

```json
{
  "schema": "jcheng.lerobot-export.v1",
  "lerobot_version": "0.7.0",
  "codebase_version": "v3.0",
  "source": {"dataset_id": "...", "root_sha256": "sha256:..."},
  "fps": 10,
  "mode": "images",
  "sample_policy": "strict",
  "dropped_frames": 3,
  "held_frames": 0,
  "time_compression": 0.975,
  "source_tick_map": "tick_map.jsonl",
  "feature_map": {"observation.state": "observation.state", "action": "action"}
}
```

`info.json` 不写 JCHENG 字段（LeRobot 会丢弃未知字段）；所有扩展信息只在
`jcheng/` sidecar。

## 12. 校验不变量（必须始终成立）

1. `SHA256SUMS` 覆盖除自身外的全部文件；数据集内任何文件都不包含
   `SHA256SUMS` 的哈希或包含自身的总字节数（无循环、无不动点）。
2. 每个 `frame_index` 恰好一行；行号与索引一致。
3. 每个 `cameras[].key` 在每帧要么有完整图像条目，要么被标 `camera_missing`。
4. `state.names`/`action.names` 与 profile 逐位相等；任何置换 = error。
5. 每维都有单位；`own-real/simulation/synthetic` 的 state/action 必须 SI。
6. `source_class` 只有一个；类特定字段缺失 = error。
7. `own-real` 没有 `authorization_ref` = error；M1 不产生 own-real。
   `state.truth_source=bus_read` 时必须有 `measurements.jsonl`，否则 error。
8. 任何 NaN/Inf = error；任何缺失图像（required）= error。
9. 导出后的 `LeRobotDataset` 长度/任务/数值必须与原生一致；否则拒绝导出。
10. 任何失败不得自动修复；只能重新导出新 `dataset_id`。

## 13. 版本与兼容

- `schema` 字符串带主版本；不兼容变更 = 新字符串（如
  `jcheng.dataset.v2`），旧文件继续按 v1 读取。
- 新增可选字段 = 次版本，读取器忽略未知可选字段；新增必填字段 = 主版本。
- LeRobot 侧 pin `0.7.0` / `codebase_version v3.0`；升级必须重跑 compat
  suite，并更新 `docs/m1/02-LEROBOT-RESEARCH.md` 的基线。
- 原生格式不承诺与 LeRobot 版本同步；适配器负责差异。

## 14. 示例：Gate-2 与 Piper X 的关键差异

```yaml
# Gate-2（无夹爪，2 维）
robot: {adapter_id: gate2_arm, dof: 2, has_gripper: false}
action:
  space_id: gate2_arm.joint_position_absolute.v1
  names: [joint1, joint2]
  units: [rad, rad]
  gripper: null
```

```yaml
# Piper X（6 关节 + prismatic 夹爪，7 维）
robot: {adapter_id: piper_x, dof: 6, has_gripper: true}
action:
  space_id: piper_x.joint_position_absolute.v1
  names: [joint1, joint2, joint3, joint4, joint5, joint6, gripper]
  units: [rad, rad, rad, rad, rad, rad, m]
  gripper: {name: gripper, space: linear, closed: 0.0, open: 0.1}
```

两者不能共用动作空间 ID；`piper_x → armpi_ultra` 的前 5 维即使“看起来
对应”，也必须显式 map，并标注 `transfer_claim: none`。

## 15. 跨仓库接口边界

| 仓库 | 与 M1 数据契约的关系 | 现在是否需要契约变更 |
|---|---|---|
| `jcheng-interfaces` | 未来 `jcheng.dataset.v1` 若被多仓库写入，需在此定义 | 否（M1 不跨仓库） |
| `jcheng-system` | 只提供 `RobotState`/`MotionCommand` 语义参考；M1 不调用 | 否 |
| `jcheng-perception` | 提供相机 key、标定 ID、频率事实；不共享文件格式 | 否 |
| `jcheng-simulation` | 提供 `robot.yaml` 与未来仿真 episode；profile 引用其哈希 | 否（仅引用） |
| `jcheng-teleop` | 未来写 episode 的生产者；一旦写，契约跨仓库 | **是，需提案** |
| `jcheng-applications` | 只消费 M2+ 的 policy artifact；M1 无产物 | 否 |
| `jcheng-benchmark` | M2 评测；不消费 M1 质量报告 | 否 |

提案触发条件（任一满足）：

1. teleop 或 simulation 要在自己的仓库里直接写 `jcheng.dataset.v1`；
2. system 要把 episode 导出作为运行时能力；
3. benchmark 要直接读质量报告做门禁。

在此之前，`jcheng.dataset.v1` 只属于 `jcheng-learning`，其他仓库不得依赖。

## 16. 开放问题（与 03-DESIGN §9 对应）

1. 是否接受双层模型（D1）。
2. ArmPi 6 维动作空间与 canonical 夹爪（D2）。
3. own-real `commanded` 状态是否允许入库但禁止训练（D3）。
4. 公开数据集选择（D4）。
5. 核心零 torch（D5）。
6. M1 默认 images（D6）。
7. 是否现在提交 interfaces 提案（D7）。
