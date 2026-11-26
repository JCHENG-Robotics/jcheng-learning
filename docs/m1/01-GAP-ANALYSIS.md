# 01 — 现状审查与 M1 缺口分析

> 状态：历史审查记录（2026-11-26）。M1 实现完成后保留，用于对照缺口；
> 当前状态见 [ACCEPTANCE.md](../../ACCEPTANCE.md)。
> 审查对象：`jcheng-learning` 全仓库；交叉核对 `jcheng-interfaces`、
> `jcheng-system`、`jcheng-perception`、`jcheng-simulation`、
> `jcheng-applications`、`jcheng-benchmark`、`jcheng-teleop` 的文档与契约。

## 1. 审查方法

| 步骤 | 做法 | 结果 |
|---|---|---|
| 仓库清点 | `git log`、`find`、逐份阅读根文档与 `docs/` | 3 个提交，M0 scaffold 完整 |
| 基线复跑 | `pytest -q tests`、`bash scripts/check_repo_gate.sh` | 13 passed；gate OK（2026-11-26） |
| 跨仓库核对 | 读 `jcheng-interfaces` 的 schema/msg/srv、teleop INPUT/ARCHITECTURE、applications TASK_ENGINE §10、perception TOPICS/DATASET、simulation robot catalog | 见 §5–§6 |
| 上游调研 | 克隆 LeRobot `v0.7.0`（commit `410c095`），读源码/docs；读真实公开数据集 `meta/` 与 Parquet schema | 见 [02-LEROBOT-RESEARCH.md](02-LEROBOT-RESEARCH.md) |

## 2. 现有仓库能力

### 2.1 已存在且可复用的部分

| 能力 | 位置 | 评价 |
|---|---|---|
| L3 定位与“离线、无硬件”边界 | `capability.yaml`、`README.md` §Scope、`docs/ARCHITECTURE.md` | 边界清晰，M0 已用静态扫描固化 |
| 文档集与状态词汇 | `README*.md`、`ROADMAP.md`、`ACCEPTANCE.md`、`CHANGELOG.md` | 符合组织文档标准；根文档英文 |
| 仓库门禁 | `scripts/check_repo_gate.sh` | 文档集、LICENSE、secret、权重、录制数据、超大文件、相对链接、测试 |
| 无硬件静态测试 | `tests/test_no_hardware.py` | 禁止设备/运动 token；可扩展 |
| 契约静态测试 | `tests/test_contract.py` | manifest、版本、contract hash、文档集、状态词汇 |
| 数据集边界提案 | `docs/DATA.md` | 目录契约、manifest 草案、完整性规则、M1 退出条件 |
| 集成边界提案 | `docs/INTEGRATION.md` | M3 意图面、lease、失败语义；M1 无运行时 |
| M0 证据 | `evidence/20261126_scaffold/` | gate.txt + CI run |

### 2.2 尚不存在

| 能力 | 现状 | 影响 |
|---|---|---|
| Python 包/`pyproject.toml` | 不存在；测试只依赖 `PyYAML` | 无法安装 CLI、无法锁依赖 |
| 数据集 Schema 的可执行定义 | 只有 `docs/DATA.md` 草案 | 无法自动校验 |
| 原生记录格式的读写器 | 无 | 合成/历史/遥操作数据没有落点 |
| 校验器与质量报告 | 无 | 无法接受或拒绝数据集 |
| Robot Profile / Action Space | 无 | 无法约束关节顺序、维度、单位 |
| LeRobot 适配器 | 无 | 无法导入公开数据或导出训练集 |
| Provenance 记录 | 只有文档字段草案 | 无法区分 synthetic / simulation / public-real / own-real |
| CLI | 无 | 无检查、转换、统计、报告入口 |
| M1 测试 fixture 与证据 | 无 | 无法证明转换一致性与异常识别 |

## 3. 现有 M1 定义 vs 本轮要求

| 维度 | 现有 `ROADMAP.md` M1 | 本轮用户要求 | 差距 |
|---|---|---|---|
| 范围 | dataset manifest + integrity gate | Schema、Adapter、Validator、Action Space、Provenance、Offline Pipeline、CLI | 大幅扩展 |
| 数据来源 | 一个导出的 episode set | 公开数据集、合成、仿真、历史、未来遥操作 | 需要多来源适配 |
| 动作空间 | 未提 | 明确映射，禁止隐式转换 | 新增核心模块 |
| 异常检查 | 缺失/时间戳/哈希 | 维度、NaN/Inf、关节顺序、缺失图像、单位、异常值 | 检查项显著增加 |
| 证据 | accepted/rejected 各一个 | 结构化质量报告 + 验收证据 + 量化一致性 | 需要报告 schema |
| 依赖 | 仅 pytest/PyYAML | 锁定版本、可复现 | 需要 lock + CI 安装策略 |

结论：**M1 需要重基线**。建议保留原 M1 的“integrity gate”作为子集，新增的
工作包作为 M1 的正式范围；M2/M3/M4 的定义不变。

## 4. 缺口清单（G1–G12）

| ID | 缺口 | 严重度 | M1 处置 |
|---|---|---|---|
| G1 | 没有可执行的 dataset/episode/frame schema | 高 | `04-DATA-CONTRACT.md` 冻结 `jcheng.dataset.v1` / `jcheng.episode.v1` |
| G2 | 没有机器人抽象，易把 ArmPi 硬编码进数据层 | 高 | `robot-adapter.yaml` + 3 个 profile（ArmPi / Gate-2 / Piper X） |
| G3 | 没有动作空间与关节顺序的显式契约 | 高 | 动作空间 ID + `names/units` 全量声明；置换必须报错 |
| G4 | 没有单位/夹爪约定检查 | 高 | own/sim/synth 强制 SI；公开导入保留源单位并标 `si_conformant: false`；canonical 夹爪与 raw `r_joint` 分离 |
| G5 | 没有时间戳模型（多流、异构频率） | 高 | 会话单调时钟 + 每流 stamp + skew/抖动检查 |
| G6 | 没有 commanded vs measured 的分离 | 高 | `state.truth` 必填；`measurements.jsonl` 独立 |
| G7 | 没有 provenance 与来源分级 | 高 | `source_class` 四类 + 类特定必填字段 |
| G8 | 没有 LeRobot 读取器（不想为了读元数据装 torch） | 中 | 独立 pyarrow 读取器 + 版本门 |
| G9 | 没有 LeRobot 写入路径 | 中 | 可选 `[lerobot]` extra，调用官方 `LeRobotDataset.create` |
| G10 | 没有质量报告 schema | 中 | `jcheng.dataset-quality-report.v1` + Markdown |
| G11 | 没有 CLI 与退出码 | 中 | `jcheng-dataset` 子命令与 0/1/2/3/4 退出码 |
| G12 | 没有依赖锁定与 CI 安装策略 | 中 | `uv.lock` + `uv sync --frozen`；核心 CI 不装 torch |

## 5. 跨仓库边界事实

### 5.1 接口仓库（L1）

- `jcheng-interfaces` v0.1.0，contract hash
  `sha256:0b8d72…24b42`；`interface_manifest.json` 覆盖 14 个 msg、10 个 srv、
  1 个 action、9 个 schema。
- 与学习相关的现有类型：
  - `MotionCommand.msg`：`kind`（`JOINT_TRAJECTORY | JOINT_STEP | POSE | HOME |
    BASE_PULSE | GRIPPER`）、`profile`、`verify_bus`、`expected_profile_hash`；
  - `JointTrajectory.msg` / `JointTrajectoryPoint.msg`：`joint_names` 顺序必须
    与 `positions` 对齐，SI 单位；
  - `GripperCommand.msg`：**canonical positive radians：0.0 闭合、2.22 张开**；
  - `RobotState.msg`：`truth` 字段显式 `measured | commanded`，
    `verification` 为 `bus | timed | open_loop`；
  - `ControlLease.msg`：优先级 `100 operator / 60 application / 40 teleop /
    20 learning / 10 diagnostics`。
- **没有** dataset/episode/robot-adapter 的 schema。M1 不新增接口；若未来
  teleop/simulation 直接生产 episode，必须先提案到 interfaces（见 §7）。

### 5.2 系统仓库（L2）

- `jcheng-system` 是唯一运动起点，`ExecuteMotion` 只在这里；
  `MotionCommand`/`ValidateMotion`/lease/deadman/stop latch 都在系统层。
- 学习仓库在 M1 不导入、不调用、不订阅任何系统接口；M3 才发布技能意图。
- `RobotState.truth` 的存在证明系统层已经区分 commanded/measured；学习数据
  契约必须沿用同一语义，不能自造“真值”。

### 5.3 感知仓库（L3）

- 相机与标定归 perception：D435i 外部视角、Aurora 腕部视角；深度/RGB 频率
  异构（D435i 深度 4–8 Hz，Aurora RGB ~12 Hz / 深度 ~8 Hz）。
- `docs/DATASET.md` 是 **YOLO 检测/关键点数据集**工具链，不是机器人 episode
  数据集；两者不合并、不互相替代。
- 学习数据只引用相机 key、分辨率、帧率与标定 ID；不打开设备、不重建 TF。

### 5.4 仿真仓库（SIM）

- `jcheng-simulation` 的 `robots/<id>/robot.yaml`
  （`schema: jcheng.simulation_robot.v1`）是仿真侧设备目录：ArmPi Ultra
  （5 revolute + `r_joint`）、Gate-2（2 revolute）、Piper X（6 revolute +
  prismatic `gripper`）。
- 仿真数据带 `/sim/truth/source=simulated`，永不作为硬件证据。
- 学习侧 Robot Profile 可以**引用**该文件的哈希，但不能把 learning 反向
  依赖 simulation 运行时。

### 5.5 应用仓库（L4）

- `jcheng-applications` 的 `TASK_ENGINE.md` §10 已定义 learned policy 边界：
  - 只接受 `params` / `skill` 两类 proposal；
  - `policy_hash` 必填，缺失/不匹配拒绝；
  - `pose`、`joint_target`、`action_chunk` 属于 **reserved**，需要
    interfaces schema + 安全评审 + 契约 bump + 文档修订。
- 因此 M1 的数据/动作空间**不能**被 applications 直接消费；M1 只产出离线
  数据与（M2 之后的）模型卡。

### 5.6 评测仓库（BENCH）

- `jcheng-benchmark` 是独立、只读、预注册 suite 的评测器；输入是 JSONL，
  输出是 report，不参与训练。
- 学习仓库 M2 的训练指标不能替代 benchmark 的正式验收；M1 的质量报告也
  不是 benchmark report，两者 schema 不混用。

### 5.7 遥操作仓库（L3，2026-11-26 新建）

- `jcheng-teleop` 已有 `TeleopCommand.msg`（关节速度 / 笛卡尔速度 + deadman），
  但**没有夹爪字段**；M1 不依赖 teleop。
- 未来 teleop 采集的 episode 应写 `jcheng.dataset.v1`；这会把数据契约变成
  跨仓库契约（见 §7）。

## 6. 与数据设计直接相关的硬事实

| 事实 | 来源 | 对 M1 的影响 |
|---|---|---|
| ArmPi `/joint_states` 是命令缓存，不是测量 | `docs/ARCHITECTURE.md` §1；`DATA.md` §4 | `state.truth` 必填；own-real 若只有缓存则 `degraded` |
| 总线读 `GetBusServoState` 无安全超时，读频率有限 | 仓库 `DATA.md` §4；系统/基线证据 | measured 状态可能是低频；数据集必须允许异构频率 |
| 夹爪有两套约定：`r_joint` raw `-2.22…0.0`（增大闭合）与 canonical `0.0 闭合 / 2.22 张开` | `GripperCommand.msg`；基线 `hardware_inventory.md` | 必须显式 `gripper.space`，禁止隐式取反 |
| ArmPi 无编码器、无 IMU、无 e-stop | 工作区 `AGENTS.md` §7；记忆条目 | 数据集不得声称“measured”除非有总线读；不得把学习输出当安全保证 |
| 相机频率异构：D435i 深度 4–8 Hz、Aurora RGB ~12 Hz / 深度 ~8 Hz | `jcheng-perception/config/cameras.yaml` | 单 fps 导出必须 `strict` 对齐或显式 `hold` |
| 动作向量维度：ArmPi 6（5 关节 + 夹爪）、Gate-2 2、Piper X 7（6 关节 + prismatic 夹爪） | 仿真 `robot.yaml` | 不能按维度猜机器人；动作空间 ID 必须带机器人身份 |
| 机器人运行时是 Humble + Python 3.10 | 工作区 `AGENTS.md` §4 | LeRobot 0.7 需要 Python ≥3.12，M3 推理节点不能直接跑在机器人系统 Python 上 |
| 训练机 GPU 为 6 GB 3060 Laptop | `nvidia-smi`（2026-11-26） | SmolVLA 微调显存未验证；M2 必须先做 MVE，不预设可行 |

## 7. 边界结论

1. **M1 不新增跨仓库契约。** `jcheng.dataset.v1` 先定义在
   `jcheng-learning/docs/`，只有本仓库的合成生成器、公开数据导入器和未来
   导出器使用。
2. **一旦 teleop / simulation / system 需要直接写 episode**，数据契约就必须
   提案到 `jcheng-interfaces`，并获得新的 contract hash；在此之前，其他仓库
   不得依赖该格式。
3. **M1 不接触 perception 的 YOLO 数据集**；两者只在“相机 key / 标定 ID”
   这一层共享命名，不共享文件格式。
4. **M1 不产生任何可被 applications 消费的产物**；policy proposal 是 M2+
   的事情，且受 `TASK_ENGINE.md` §10 的 reserved 规则约束。
5. **M1 的所有证据都是 L0/L1**（静态/单元），不是 L4 replay，更不是 L5
   硬件验证。

## 8. 审查发现的小问题（实现阶段顺手修，不在本轮改）

| 位置 | 问题 | 处置 |
|---|---|---|
| `docs/ARCHITECTURE.md` §2 | “1. external storage …;2. an integrity gate” 缺少换行 | 实现阶段文档修订 |
| `docs/DATA.md` §2 | 目录契约仍写 `observations/ commands/ measurements/`，与 LeRobot 无关 | 由 `04-DATA-CONTRACT.md` 替换并冻结 |
| `README.md` “Dataset, training or inference capability” | 仍是 Unverified | M1 完成后按证据更新 |
| `ROADMAP.md` M1 退出条件 | 只覆盖 manifest + checker | 审批后重基线为 7 个工作包 |
