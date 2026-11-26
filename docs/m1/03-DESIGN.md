# 03 — M1 架构、依赖、实施计划与验收设计

> 状态：设计已批准；S1–S5 已于 2026-11-26 实现（v0.2.0）。证据见
> [evidence/20261126_m1/](../../evidence/20261126_m1/README.md)。§12 记录
> 实施偏差。
> 数据格式的规范性定义见 [04-DATA-CONTRACT.md](04-DATA-CONTRACT.md)；
> 上游事实与来源见 [02-LEROBOT-RESEARCH.md](02-LEROBOT-RESEARCH.md)。

## 1. 设计原则

1. **证据与训练分离。** JCHENG 原生格式是审计/校验/溯源的事实源；LeRobot v3
   是训练交换格式。训练永远读 LeRobot，不读原生格式。
2. **不重写 LeRobot。** Parquet/MP4 写入、统计、归一化、训练循环全部调用
   官方实现；本仓库只做“转换 + 校验 + 报告”。
3. **不隐式转换。** 关节顺序、单位、夹爪约定、动作表示、时间基准必须显式
   声明；任何置换/缩放/取反都必须有映射记录。
4. **失败关闭。** 校验失败的数据集终止（terminal），不自动修复；修复只能是
   重新导出并产生新的 `dataset_id`。
5. **离线优先。** 核心路径不需要 ROS、不需要 torch、不需要机器人、不需要
   网络；公开数据集导入是显式的、可 pin revision 的可选步骤。
6. **不过度抽象。** M1 只有四个适配器（native 读/写、LeRobot 读/写），
   不做插件注册表、不做多后端存储、不做流式训练。

## 2. 总体架构

```text
                     ┌─────────────────────────────────────────────┐
  合成生成器 ────────▶│  JCHENG 原生 episode 存储（jcheng.dataset.v1）│
  公开数据集导入 ────▶│  dataset.yaml · provenance.json · SHA256SUMS │
  未来 teleop/仿真 ──▶│  episodes/<id>/{meta.json,frames.jsonl,images}│
                     └───────────────┬─────────────────────────────┘
                                     │ 只读
                     ┌───────────────▼─────────────────────────────┐
                     │  Validator（ROS-free）                       │
                     │  布局/时间/关节/单位/图像/数值/溯源/交叉检查   │
                     └───────────────┬─────────────────────────────┘
                                     │ 质量报告（JSON + Markdown）
                     ┌───────────────▼─────────────────────────────┐
                     │  LeRobot v3 exporter（可选 extra）            │
                     │  LeRobotDataset.create/add_frame/finalize    │
                     └───────────────┬─────────────────────────────┘
                                     │
                     ┌───────────────▼─────────────────────────────┐
                     │  LeRobot v3 数据集（外部存储）+ jcheng/ sidecar│
                     └───────────────┬─────────────────────────────┘
                                     │ M2 训练（不在 M1）
                     ┌───────────────▼─────────────────────────────┐
                     │  SmolVLA / 其他策略（operator laptop GPU）    │
                     └─────────────────────────────────────────────┘
```

数据流方向是单向的：原生 → 校验 → LeRobot。公开数据集是反向的
LeRobot → 原生（导入后重新校验），但导入结果仍以原生格式为准。

## 3. 模块设计

### 3.1 包结构

```text
jcheng-learning/
├── pyproject.toml                    # 包元数据、console script、可选 extra
├── uv.lock                           # 全量锁（含 extra 的解析结果）
├── src/jcheng_learning/
│   ├── __init__.py
│   ├── version.py
│   ├── errors.py                     # 退出码与异常类型
│   ├── provenance.py                 # git/lock/software helpers
│   ├── io/
│   │   ├── jsonl.py                  # 流式读写 + 行号错误
│   │   ├── hashing.py                # SHA256SUMS / root hash
│   │   ├── image.py                  # PNG 解码/编码/校验（Pillow）
│   │   └── yaml_io.py
│   ├── native/
│   │   ├── reader.py                 # 原生只读
│   │   └── writer.py                 # 原生写入（合成/未来 teleop）
│   ├── lerobot/
│   │   ├── v3_reader.py              # 独立 pyarrow 读取（不需要 torch）
│   │   ├── imports.py                # 公开数据 → 原生
│   │   ├── export.py                 # 调用官方 LeRobotDataset
│   │   └── features.py               # 原生 ↔ LeRobot 特征映射
│   ├── validate/
│   │   └── engine.py                 # DQ-* 检查、聚合与报告
│   ├── profiles/
│   │   ├── registry.py
│   │   ├── armpi_ultra.yaml
│   │   ├── gate2_arm.yaml
│   │   ├── piper_x.yaml
│   │   ├── so101_follower.yaml       # 公开数据导入用
│   │   ├── pusht_2d.yaml             # 公开基准
│   │   └── probe_2d.yaml             # 测试 fixture
│   ├── action_maps/
│   │   └── armpi_ultra_raw_to_canonical.yaml
│   ├── action_map.py                 # 显式映射执行器
│   ├── synthetic.py                  # 确定性生成器
│   ├── report.py                     # JSON/Markdown 渲染
│   └── cli.py                        # jcheng-dataset
│   └── schemas/                      # 报告 JSON Schema（package data）
├── tests/
│   ├── fixtures/                     # 小型合成/公开数据 fixture
│   ├── test_action_map.py
│   ├── test_profiles.py
│   ├── test_synthetic.py
│   ├── test_native_roundtrip.py
│   ├── test_validate.py
│   ├── test_cli.py
│   ├── test_import.py
│   ├── test_lerobot_reader.py
│   ├── test_export_features.py
│   ├── test_no_hardware.py           # 扩展
│   └── test_contract.py              # 保持
├── docs/m1/                          # 本设计包（中文）
└── evidence/                         # 实现阶段生成
```

不引入插件系统；适配器是四个具体类，接口只在内部使用。

实现偏差：没有独立的 `schema/` 包；`dataset.yaml`/`episode`/`profile`/
`action-map` 的约束由 `profiles/registry.py`、`native/writer.py` 和
`validate/engine.py` 以代码级校验执行。只有质量报告保留独立 JSON Schema
（`schemas/jcheng.dataset-quality-report.v1.schema.json`）。

### 3.2 原生数据层

- `NativeDatasetWriter`：`begin_episode / add_frame / end_episode / finalize`。
  M1 同步写、单线程，不引入异步图像写入；确定性优先。
- `NativeDatasetReader`：只读，流式逐行解析 `frames.jsonl`，记录行号，
  出错时给出 `file:line`。
- 写入顺序：先写 `episodes/**`，再写 `dataset.yaml`，再写
  `provenance.json`，最后生成 `SHA256SUMS`。
- 不自动创建 `dataset_id` 的“最新版本”指针；数据集是不可变目录。

### 3.3 Robot Profile

上游来源（只引用，不复制文件）：

1. `jcheng-simulation` 的 `robots/<id>/robot.yaml`（仿真/几何/限位）；
2. `jcheng-system` 的 robot profile（部署时的伺服映射/安全限位）。

学习侧 `robot-adapter.yaml` 是**消费方**：记录上游路径与 SHA-256，并把
规范化后的 `names/units/limits` 冻结成学习快照；上游或快照变化必须新建
profile 版本，不能原地改。
M1 内置 4 个生产 profile（实现另含 `pusht_2d` 公开基准 profile 与 `probe_2d`
测试 fixture profile）：

| profile id | DoF | 夹爪 | 动作空间 | 用途 |
|---|---|---|---|---|
| `armpi_ultra` | 5 | revolute `r_joint`，canonical 0…2.22 | 6 维 `joint_position_absolute` | 目标平台 |
| `gate2_arm` | 2 | 无 | 2 维 | 最小回归 |
| `piper_x` | 6 | prismatic `gripper` 0…0.1 m | 7 维 | 未来平台 |
| `so101_follower` | 5 | revolute gripper（归一化） | 6 维（仅导入） | 公开数据兼容验证 |

`so101_follower` 的限位在公开数据集中没有可靠来源，profile 标
`limits.known: false`，校验器对其跳过限位检查并标记 `inconclusive`，不得
据此声称“通过限位检查”。

### 3.4 Action Space Mapping

- 动作空间 ID：`<profile_id>.joint_position_absolute.v<major>`；ID 绑定机器人，
  不允许“通用 6 维空间”。
- 映射文件 `action-map.yaml`（`jcheng.action-map.v1`）逐维声明
  `to_index/to_name ← from_index/from_name + scale/offset/unit`。
- 执行器只做三件事：按显式索引取值、仿射变换、单位换算；**不按维度猜、
  不按名字模糊匹配、不自动转置**。
- 覆盖检查：每个目标维必须恰好一条规则；源维可以 `unmapped`；重复/缺失
  目标维直接报错。
- 变换后必须重新做限位与单位检查；映射本身写入 provenance。

M1 内置两个映射：

1. `armpi_ultra.raw_joint.v1 → armpi_ultra.joint_position_absolute.v1`
   （夹爪 `r_joint` raw `-2.22…0` → canonical `0…2.22`，显式取反，offset=0）；
2. 一个仅用于测试的 `piper_x → armpi_ultra` 前 5 维 + 夹爪映射，标注
   `transfer_claim: none`，禁止用于训练声明。

**与模型动作空间的关系**：M1 不把数据集映射到某个策略的输入/输出头。
数据集的动作空间就是机器人动作空间；M2 训练时策略的 `output_features.action`
必须与数据集维度一致（SmolVLA 的 32 维补零只是网络内部对齐，不是映射）。
`rename_map` 只改 observation key，不改 action；跨机器人/跨维度必须新建
action head 并重训，禁止复用权重冒充兼容。

**Profile 是数据，不是代码**：新增机器人 = 新增一个
`robot-adapter.yaml` + 一个 registry 条目 + 一个 fixture 测试；不得在
validator 或 exporter 里写 `if robot == "armpi_ultra"` 分支。

### 3.5 Validator

检查引擎按稳定 ID（`DQ-*`）执行，严重度 `error/warning/info`，状态
`pass/fail/skip/inconclusive`。完整检查表见 §7.2。规则：

- `error` → 数据集拒绝（退出码 1）；
- `warning` → `degraded`（退出码 0，但报告标 `usable_for_training: false`
  除非策略显式接受）；
- `skip` → 不适用的检查（如无夹爪）；
- `inconclusive` → 缺依赖/缺信息（退出码 4），**不能算通过**。
- 聚合优先级：`fail > inconclusive > degraded > pass`。

### 3.6 Quality Report

`jcheng.dataset-quality-report.v1`，包含：

```json
{
  "schema": "jcheng.dataset-quality-report.v1",
  "dataset": {"id": "...", "root_sha256": "...", "source_class": "...",
               "profile_id": "...", "profile_sha256": "..."},
  "tool": {"version": "0.2.0", "git_commit": "...", "lock_sha256": "..."},
  "run": {"started_at": "...", "duration_s": 1.23, "deterministic": true},
  "summary": {"result": "pass|degraded|fail|inconclusive",
               "usable_for_training": false,
               "errors": 0, "warnings": 1, "skipped": 2, "inconclusive": 0},
  "checks": [{"id": "DQ-T04", "severity": "warning", "status": "pass",
               "message": "...", "counts": {...}, "samples": [...]}],
  "features": {"observation.state": {"count": 120, "min": [...], "...": "..."}},
  "episodes": [{"id": "ep_0001", "frames": 40, "duration_s": 4.0,
                 "dropped_frames": 0, "images": {"external": 40}}],
  "limitations": ["state.truth=commanded; not a measurement"]
}
```

报告不写回数据集目录；默认写到调用方指定的 `--report` 路径，或
`reports/<dataset_id>/quality-<timestamp>.json`。

### 3.7 LeRobot 适配器

**读取器（`v3_reader.py`）**：只用 `pyarrow`，不导入 torch。

```text
meta/info.json          → 版本门（必须 v3.0）、fps、features
meta/episodes/*.parquet → episode 边界、tasks、length、stats
meta/tasks.parquet      → task_index → 文本（兼容 pandas index 列）
data/**/*.parquet       → 逐 episode 的 state/action/timestamp；
                          dtype:image 的图像字节也在这里（U2 实测最终无 images/）
videos/**               → 可选解码（[video] extra）
```

读取器不“修复”数据：缺列、长度不符、索引不连续一律报错。

**导出器（`v3_exporter.py`）**：只在 `lerobot` extra 可用时导入。

```python
from lerobot.datasets.lerobot_dataset import LeRobotDataset

ds = LeRobotDataset.create(
    repo_id=f"local/{dataset_id}",
    fps=export_fps,
    features=features,
    root=tmp_dir,
    robot_type=profile_id,
    use_videos=(mode == "videos"),
)
for frame in aligned_frames:
    ds.add_frame(frame)   # frame 含 task
ds.save_episode()
ds.finalize()
# 校验 meta/info.json，写 jcheng/ sidecar，原子重命名到最终目录
```

- `repo_id` 用 `local/<dataset_id>`，不上传 Hub；上传是 M2 之后的操作员决定。
- 输出目录必须不存在；先写 `.<name>.tmp`，`finalize()` 成功后 rename。
- 导出后写 `jcheng/export.json`（LeRobot 版本、fps、mode、采样策略、
  源数据集 root hash、帧映射摘要）。

#### 3.7.1 适配器接口（方法级契约）

| 接口 | 输入 | 输出 | 失败语义 |
|---|---|---|---|
| `NativeDatasetReader.open(root)` | 原生目录 | `Dataset` 句柄 | manifest/hash 失败 → `DatasetError` |
| `NativeDatasetReader.iter_episodes()` | — | `Iterator[Episode]` | 任一帧非法 → 立即抛出（不跳过） |
| `NativeDatasetWriter.begin_episode(meta)` | episode meta | 写入器 | 目录已存在 → `DatasetError` |
| `NativeDatasetWriter.add_frame(frame)` | 帧对象 | — | 维度/单位/图像不符 → `DatasetError` |
| `LeRobotV3Reader.open(path_or_repo)` | 本地目录/Repo ID | `ForeignDataset` | 版本非 v3.0 → `InconclusiveError` |
| `LeRobotV3Importer.import_(...)` | 源 + profile + source_class + revision | `ImportResult{dataset_id, root_sha256, counts, limitations}` | 缺 profile/revision → 拒绝 |
| `LeRobotV3Exporter.export(dataset, out, fps, mode, policy)` | 原生数据集 | `ExportResult{root_sha256, dropped, held, time_compression, lerobot_version}` | 依赖缺失 → `DependencyError`；一致性失败 → `ExportError` |

异常类型只用于区分退出码：`DatasetError`→1，`UsageError`→2，
`DependencyError`→3，`InconclusiveError`→4。适配器不返回“部分成功”。

### 3.8 合成生成器

- 命令：`jcheng-dataset synth --profile armpi_ultra --out <dir> --episodes 3
  --frames 40 --fps 10 --seed 0 --created-at 2026-11-26T00:00:00+08:00`。
- 数值：内置整数 LCG，不依赖 `random` 的实现细节；关节用正弦 + 小噪声，
  动作 = 下一帧状态 + 偏置（保证可复现），夹爪开合分段。
- 图像：确定性渐变 + 移动方块，Pillow 写 PNG；分辨率 64×48（小、快），
  但 profile 声明真实分辨率 640×480，生成器允许 `--image-size` 覆写并在
  manifest 记录实际尺寸。
- 异常 fixture：同一生成器加 `--anomaly <name>`，只用于测试；异常数据
  永不进入 `evidence/` 的正向数据集。

### 3.9 离线数据管线：四类来源

| 来源 | M1 入口 | 实现程度 | 证据声明 |
|---|---|---|---|
| 合成 | `jcheng-dataset synth` | 完整实现 | synthetic；无硬件声明 |
| 公开数据集 | `jcheng-dataset import <repo_id>` | 完整实现（v3.0） | public-real 或 simulation + `origin.public: true` |
| 历史记录 | `jcheng-dataset import --format native` | 只接受已符合 v1 的目录；不解析基线实验 JSON/CSV | 按原 `source_class` 继承 |
| 未来遥操作 | `NativeDatasetWriter` API | 只冻结写入契约；采集器在 teleop 仓库 | own-real（M3+，需授权） |

历史记录的判断：冻结基线 `jcheng-manipulation` 里的 `evidence/*.json`、
`trials_export.csv` 是实验记录，不是 episode（没有逐帧 state/action/相机），
不能冒充训练数据。M1 提供 `NativeDatasetWriter` 与 `--format native` 导入；
具体历史格式适配器在操作员选定一份真实记录后再实现（M1.5），避免为不存在的
格式写抽象层。

未来遥操作：`jcheng-teleop` 的 `TeleopCommand` 是 50 Hz 意图流，不是 episode；
录制器必须把命令、总线实测、相机 stamp 分开写入原生格式。M1 不实现录制器，
也不订阅 DDS。

### 3.10 CLI

```text
jcheng-dataset profile list|show <id>
jcheng-dataset inspect <dataset-root>
jcheng-dataset validate <dataset-root> [--profile <id>] [--report <path>] [--json]
jcheng-dataset stats <dataset-root> [--json]
jcheng-dataset report <quality.json> --format md|json
jcheng-dataset import <lerobot-root|repo_id> --format lerobot|native
                    --out <dir> [--profile <id>] [--source-class <class>]
                    [--revision <sha>] [--no-images]
jcheng-dataset convert <dataset-root> --to lerobot --out <dir>
                    [--mode images|videos] [--fps N] [--sample-policy strict|hold]
jcheng-dataset synth --profile <id> --out <dir> [--seed N] [--anomaly <name>]
jcheng-dataset hash <dataset-root>
```

退出码：

| 码 | 含义 |
|---|---|
| 0 | pass 或 degraded（报告里区分） |
| 1 | fail（存在 error） |
| 2 | 用法/参数错误 |
| 3 | 缺少可选依赖（`lerobot`/`av`） |
| 4 | inconclusive（信息不足，不能算通过） |

## 4. 关键规则

### 4.1 时间模型与采样

- 原生时间统一为 **会话单调时钟 int64 纳秒**；episode 记录 `start_ns/end_ns`；
  墙钟时间只在 manifest 的 `created_at/started_at` 出现，不参与帧对齐。
- 每帧 `t_ns` 是该帧的对齐时刻；每个相机另有 `stamp_ns`（采集时刻），
  校验 `|stamp_ns - t_ns| ≤ max_skew_ns`。
- 导出网格：`export_fps` 必须是整数；目标时刻 `k/export_fps`。
- `strict`：所有 `required` 流在 `±0.5/export_fps` 内都有样本才保留该帧，
  否则丢弃并计数。丢弃后必须**重编号**为连续网格（LeRobot 要求
  `timestamp` 间隔为 `1/fps`），同时在 sidecar 记录
  `source_tick → export_index` 映射与 `time_compression`。
- `hold`：缺失流用最近的前一帧，最多 `max_hold_ms`；记录 `held_frames`
  与每帧 `age_ms`；超时仍丢弃。
- 丢弃率 > 5% 或出现 `time_compression < 0.95` → 报告 `degraded`，
  该数据集不得在未复核的情况下用于 M2 训练。
- 绝不把不同时间基准的流“对齐”为同一 `t_ns` 而不记录偏移。

### 4.2 不可变与哈希

- `dataset_id` 不可复用；修正 = 新目录 + 新 ID。
- `SHA256SUMS` 覆盖**除自身以外**的全部文件（含 `dataset.yaml`、
  `provenance.json`、`episodes/**`），按路径排序。
- 数据集内部**不保存** `SHA256SUMS` 的哈希或包含自身的总字节数，避免
  自引用/不动点；质量报告记录 `root_sha256 = SHA256(SHA256SUMS)`、
  `file_count`、`total_bytes`。
- 验收证据记录 `root_sha256`；任何篡改都会改变 root。

### 4.3 导出特征映射

| 原生 | LeRobot | 说明 |
|---|---|---|
| `observation.state` 向量 | `observation.state` | float32，`names` 来自 profile |
| `action` 向量 | `action` | float32，`names` 来自 profile |
| `images.<camera>` | `observation.images.<camera>` | `dtype: image` 或 `video` |
| episode `task` | 每帧 `task` | 逐帧传入；`tasks.parquet` 自动生成 |
| `t_ns` | `timestamp`（秒） | `(t_ns - start_ns)/1e9`，重编号后为 `k/fps` |

不导出 depth、detections、measurements、labels；这些保留在原生层，M1 不进
训练集。若未来需要，按新 feature + 新契约处理，不在 M1 偷加。

### 4.4 公开数据导入

- 必须显式 `--source-class`（`public-real` 或 `simulation`）；不从
  `robot_type` 猜。
- 必须显式 `--profile`；没有 profile 就拒绝导入（不能“无 profile 校验”）。
- 必须 pin `--revision`（HF commit）；记录 repo_id、revision、license、
  每个文件的 SHA256。
- `codebase_version != v3.0` → `InconclusiveError`（退出码 4），不做兼容解析。
- 视频解码不可用 → 图像检查 `inconclusive`，导入结果标 `images_missing`，
  不能导出为带相机的训练集。

### 4.5 确定性

- 合成数据的字节级确定性依赖“同一 venv + 锁文件 + seed + 固定 created_at”；
  报告记录 `lock_sha256` 与工具版本。
- 校验器不依赖字典遍历顺序；检查按 ID 排序；报告 JSON 用 `sort_keys=True`。
- 统计量用 `numpy` 的确定性算法；不引入多线程归约。

## 5. 依赖选型与兼容性

### 5.1 核心依赖（必须、轻量）

| 依赖 | 固定版本 | 许可 | 用途 | 兼容性 |
|---|---|---|---|---|
| Python | 3.12 | — | 运行时 | LeRobot 0.7 要求 ≥3.12；本机 3.12.3 |
| PyYAML | 6.0.2 | MIT | manifest/profile | 与 M0 CI 一致 |
| pyarrow | 24.0.0 | Apache-2.0 | Parquet 读写 | LeRobot 允许 ≥21,<30；`lerobot[dataset]` 的 datasets 5.1 要求 ≥24；已实测读 pusht（21 与 24 均可读 v3 格式） |
| numpy | 2.2.6 | BSD-3 | 统计/数值 | LeRobot 允许 ≥2.0,<2.3 |
| Pillow | 13.0.0 | HPND | PNG 编解码 | LeRobot 允许 ≥10,<14 |
| jsonschema | 4.26.0 | MIT | schema 校验 | 纯 Python |
| huggingface_hub | 2.4.0 | Apache-2.0 | 公开数据集下载/pin revision | LeRobot 允许 ≥1.31,<3 |

### 5.2 可选依赖

| extra | 依赖 | 版本 | 用途 |
|---|---|---|---|
| `video` | `av` | 15.1.0 | 解码 AV1/MP4；LeRobot 允许 ≥15,<16 |
| `lerobot` | `lerobot[dataset]` | 0.7.0 | 官方写入/读取 oracle；含 pyarrow/datasets/av，会拉 torch |
| `test` | `pytest` / `pytest-cov` | 8.3.4 / 4.1.0 | CI |

### 5.3 锁与安装策略

- `uv.lock` 覆盖核心 + 所有 extra 的解析结果；CI 用
  `uv sync --frozen`（只装核心+test），不装 torch。
- 核心 CI：`uv sync --frozen --extra test`；实现阶段按 uv 版本确认命令。
- compat 作业（laptop/手动）：`uv sync --frozen --extra lerobot --extra video`，
  记录 `uv.lock` 的 SHA256。
- 不使用系统 Python 的 numpy/PyYAML；全部在 venv 内。

### 5.4 兼容性结论

- **M1 核心路径可在无 torch、无 ROS、无 GPU 的机器上完整运行。**
- LeRobot 0.7 要求 Python ≥3.12；机器人 Humble（3.10）不具备
  运行条件，M3 需另选推理位置（laptop / 3.12 容器 / ONNX）。
- `lerobot==0.7.0` 是硬 pin；升级必须同时重跑 compat suite 并更新
  `docs/m1/02-LEROBOT-RESEARCH.md` 的版本基线。

## 6. 分阶段实施计划

> 工作量是工程估算，不是承诺；审批后按阶段提交 PR，每阶段独立可回滚。

| 阶段 | 内容 | 交付物 | 退出条件 | 估算 |
|---|---|---|---|---|
| S1 | 打包与数据层 | `pyproject.toml`、`uv.lock`、schema 模块、native reader/writer、4 个生产 profile（另加 2 个 fixture/公开 profile）、报告 JSON Schema | `jcheng-dataset synth` 能生成数据集；native 读写 round-trip 字节一致 | 0.5–1 天 |
| S2 | 校验与报告 | 全部 `DQ-*` 检查、质量报告、CLI `validate/stats/report/hash`、异常 fixture | 异常矩阵 100% 命中预期 check ID；报告通过 JSON Schema | 1–1.5 天 |
| S3 | 公开数据读取 | `v3_reader.py`、`import` 命令、provenance/license 记录、pusht CI 测试 | pusht 206 eps/25,650 frames 导入成功；state/action 与源逐值相等 | 1 天 |
| S4 | LeRobot 导出 | `v3_exporter.py`、特征映射、`strict/hold` 采样、sidecar、compat suite | 合成集导出后 `LeRobotDataset` 可加载；长度/任务/数值一致 | 1–1.5 天 |
| S5 | 验收与文档 | so101 round-trip 证据、gate/CI 更新、英文 ROADMAP/ACCEPTANCE/CHANGELOG、版本 0.2.0 | 全部验收项通过；M0 13 tests 仍过；gate 绿 | 0.5–1 天 |

总计约 **4–5.5 个工作日**（不含 M2 训练）。S4 的 compat 作业需要网络下载
86 MB so101 数据；若网络/解码失败，按 §7.4 的降级规则处理并记录
`inconclusive`，不伪造通过。

## 7. 测试矩阵与量化验收

### 7.1 测试层级

| 层级 | 内容 | 是否 CI | 证据等级 |
|---|---|---|---|
| L0 | schema、静态扫描、gate | 是 | L0 |
| L1 | 单元/CLI/合成/公开数据格式 | 是 | L1 |
| L1-compat | 真实 LeRobot 写入/读取 oracle | 手动/laptop | L1 |
| L4 | 录制数据 replay | 否（M1 无策略） | — |
| L5 | 硬件 | 否（禁止） | — |

### 7.2 检查表（Validator）

| ID | 检查 | 严重度 | 失败动作 |
|---|---|---|---|
| DQ-M01 | `dataset.yaml` 可解析且符合 schema | error | 拒绝 |
| DQ-M02 | 必需文件齐全（manifest/provenance/sums/episodes） | error | 拒绝 |
| DQ-M03 | `dataset_id` 格式/唯一性/重复发布 | error | 拒绝 |
| DQ-M04 | `SHA256SUMS` 覆盖完整且逐文件匹配 | error | 拒绝 |
| DQ-M05 | 无符号链接、绝对路径、`..` 逃逸、未列文件 | error | 拒绝 |
| DQ-M06 | episode 数、帧数、时长与 manifest 一致 | error | 拒绝 |
| DQ-M07 | 重复 episode/dataset ID | error | 拒绝 |
| DQ-M08 | profile 存在、版本/哈希匹配 | error | 拒绝 |
| DQ-T01 | 时间戳为有限非负整数 | error | 拒绝 |
| DQ-T02 | 每流时间单调不减 | error | 拒绝 |
| DQ-T03 | `frame_index` 从 0 连续 | error | 拒绝 |
| DQ-T04 | 帧周期在容差内（抖动） | warning | degraded |
| DQ-T05 | 无重复 `(stream, timestamp)` | error | 拒绝 |
| DQ-T06 | 相机 stamp 与帧时刻 skew 在界内 | error | 拒绝 |
| DQ-T07 | episode 时长 = 帧数 / fps（容差内） | warning | degraded |
| DQ-T08 | 时间基准/时钟源已声明 | error | 拒绝 |
| DQ-J01 | state/action 维度 = profile | error | 拒绝 |
| DQ-J02 | 关节名称与顺序完全一致（置换检测） | error | 拒绝 |
| DQ-J03 | 关节限位（profile 已知时） | error | 拒绝 / 未知则 inconclusive |
| DQ-J04 | 单位已逐维声明；own/sim/synth 必须 SI，公开导入须标 `si_conformant: false` | error | 拒绝 |
| DQ-J05 | 动作表示受支持（仅 absolute） | error | 拒绝 |
| DQ-J06 | 夹爪约定一致（canonical/raw 不混用） | error | 拒绝 |
| DQ-J07 | 夹爪范围与方向（未知范围则 inconclusive） | error | 拒绝 |
| DQ-J08 | 动作空间 ID 与 profile 匹配 | error | 拒绝 |
| DQ-J09 | 同一数据集不混用动作空间 ID | error | 拒绝 |
| DQ-V01 | 所有数值有限（无 NaN/Inf） | error | 拒绝 |
| DQ-V02 | state/action 幅值在 profile 限位 × slack 内 | error | 拒绝 |
| DQ-V03 | 常量/退化通道 | warning | degraded |
| DQ-V04 | 速度与位置差分一致（有速度时） | warning | degraded |
| DQ-V05 | 离群值（z-score） | warning | degraded |
| DQ-V06 | 单帧动作跳变超界 | error | 拒绝 |
| DQ-I01 | 每帧每相机都有图像 | error | 拒绝 |
| DQ-I02 | 文件存在、非空、可读 | error | 拒绝 |
| DQ-I03 | 图像可解码 | error | 拒绝 / 缺依赖则 inconclusive |
| DQ-I04 | 宽高/通道与声明一致 | error | 拒绝 |
| DQ-I05 | dtype/取值范围（uint8） | error | 拒绝 |
| DQ-I06 | 非全黑/全白（方差 > 0） | warning | degraded |
| DQ-I07 | 图像 stamp 存在且与帧对齐 | error | 拒绝 |
| DQ-I08 | 重复图像（哈希） | warning | degraded |
| DQ-I09 | 视频帧数 = episode 长度（视频模式） | error | 拒绝 / 无解码器则 inconclusive |
| DQ-P01 | `source_class` ∈ 四类 | error | 拒绝 |
| DQ-P02 | 类特定必填字段齐全；`truth_source=bus_read` 必有 measurements | error | 拒绝 |
| DQ-P03 | 转换链哈希可追溯 | error | 拒绝 |
| DQ-P04 | 许可证/同意记录（public-real/own-real） | error | 拒绝 |
| DQ-P05 | own-real 有授权引用；无硬件声明 | error | 拒绝 |
| DQ-P06 | 工具版本、git commit、lock hash 记录 | error | 拒绝 |
| DQ-P07 | `truth_source` 与 `source_class`/measurements 一致；`truth:mixed` 禁止 | error | 拒绝 |
| DQ-X01 | train/val 划分无重叠 | error | 拒绝 |
| DQ-X02 | 重复 episode 内容 | warning | degraded |
| DQ-X03 | 声明统计与重算一致 | error | 拒绝 |
| DQ-X04 | 导出 round-trip 一致性 | error | 拒绝导出 |
| DQ-X05 | task 非空且 episode 内一致 | warning | degraded |
| DQ-X06 | episode 长度边界（≥2 帧、≤配置上限） | error | 拒绝 |

### 7.3 验收标准（量化）

| ID | 标准 | 证据 |
|---|---|---|
| A1 | 无机器人连接完成全部核心测试；公开数据集测试标记 `network`，可用预下载目录离线复跑 | CI 日志；`pytest -m "not network"` |
| A2 | 合成数据两次生成（同 seed/固定 created_at）`root_sha256` 相同 | 两次 `sha256sum` + 测试 |
| A3 | `pusht` 导入：206 eps、25,650 frames；state/action 与源逐值相等（float32） | 导入测试 + 报告 |
| A4 | `svla_so101` 导入→导出→官方 `LeRobotDataset` 加载：50 eps、11,939 frames；state/action float32 位级相等（或 ≤1 ULP） | compat 证据（laptop） |
| A5 | 图像模式从嵌入图像解码后逐像素相等；视频模式 PSNR ≥ 40 dB | 测试/证据 |
| A6 | 17 类异常各自命中预期 check ID，退出码 1，无崩溃 | 异常矩阵报告 |
| A7 | 4 类 `source_class` 的 schema/校验路径都有测试；M1 实际产生 synthetic/simulation/public-real，own-real 仅用 fixture 验证规则，不声称采集 | provenance 测试 |
| A8 | `uv sync --frozen` 成功；报告含 `lock_sha256`；同一 lock 两次运行结果一致 | CI + 报告 |
| A9 | 质量报告通过 `jcheng.dataset-quality-report.v1` JSON Schema，Markdown 可读 | schema 测试 |
| A10 | M0 13 个测试全部通过；gate 通过；无设备/运动 token；核心路径不 import torch | CI + 静态扫描 |
| A11 | 无任何真实硬件运动执行路径（M1 不订阅/不发布/不调用系统接口） | 静态扫描 + 代码审查 |

### 7.4 一致性容差（转换前后）

| 数据 | 容差 | 判定方式 |
|---|---|---|
| `observation.state` / `action` 数值 | float32 位级相等；若原生由 double 生成，则 ≤ 1 ULP | Parquet 读回 vs 原生 JSON，逐值比较 |
| 关节名称/顺序/维度 | 完全相等 | 字符串列表逐位比较 |
| `timestamp` | 与 `k/fps` 的误差 ≤ 1e-9 s | LeRobot `timestamp` vs 导出网格 |
| episode 数 / 每集帧数 | 完全相等 | `meta/info.json`、`meta/episodes` vs manifest |
| task 文本 | 完全相等 | 每帧 `task` vs 原生 episode task |
| 图像（images 模式） | 逐像素相等（RGB8） | 从 Parquet 嵌入图像解码为 uint8 后比较（不要用 loader 的 float32 视图） |
| 图像（videos 模式） | PSNR ≥ 40 dB，帧数相等 | 解码后逐帧计算 |
| 动作空间 ID / 单位 | 完全相等 | 导出 sidecar vs manifest |

不允许“平均误差很小”代替逐值检查；任何超差即导出失败（DQ-X04）。

### 7.5 异常矩阵（必须全部命中）

| # | 注入的异常 | 期望检查 ID | 期望退出码 |
|---|---|---|---|
| 1 | state 出现 NaN | DQ-V01 | 1 |
| 2 | action 出现 +Inf | DQ-V01 | 1 |
| 3 | state 少一维 | DQ-J01 | 1 |
| 4 | action 多一维 | DQ-J01 | 1 |
| 5 | 交换 joint2/joint3 顺序 | DQ-J02 | 1 |
| 6 | 缺失一帧 `external` 图像 | DQ-I01 | 1 |
| 7 | PNG 截断/不可解码 | DQ-I03 | 1 |
| 8 | 图像宽高与声明不符 | DQ-I04 | 1 |
| 9 | 时间戳回退 | DQ-T02 | 1 |
| 10 | 重复 `(stream,timestamp)` | DQ-T05 | 1 |
| 11 | own-real 使用 `deg` 且 `si_conformant: true` | DQ-J04 | 1 |
| 12 | 同一数据集混用 canonical/raw 夹爪 | DQ-J06 | 1 |
| 13 | SHA256SUMS 与文件不符 | DQ-M04 | 1 |
| 14 | manifest 列出的文件不存在 | DQ-M05 | 1 |
| 15 | `source_class: own-real` 缺 `authorization_ref` | DQ-P05 | 1 |
| 16 | `truth_source: bus_read` 但无 measurements | DQ-P02 | 1 |
| 17 | `source_class: simulation` 却用 `generator_truth` | DQ-P07 | 1 |

### 7.6 降级/失败规则

- 视频解码不可用：DQ-I03/I09 → `inconclusive`，退出码 4；不能用
  “图像模式通过”替代视频兼容性声明。
- 官方 LeRobot 不可安装：A4 保持 `inconclusive`，M1 不能宣称“与 LeRobot
  0.7 双向兼容”；只能在报告中记录“读取器兼容 v3.0 格式”。
- 公开数据集下载失败：CI 作业失败，不允许跳过而不记录；本地验收可用
  预下载目录 + `--revision` 校验。
- 任何一项验收失败：M1 不通过，不进入 M2。

### 7.7 M1 证据清单（实现阶段生成）

| 文件 | 内容 | 生成方式 |
|---|---|---|
| `evidence/<date>_m1/README.md` | 命令、版本、lock hash、数据集 revision、结果摘要（英文） | 手工汇总 |
| `evidence/<date>_m1/gate.txt` | `check_repo_gate.sh` 输出 | 本机/CI |
| `evidence/<date>_m1/pytest.txt` | `pytest -q` 与 `pytest -m "not network"` 输出 | CI |
| `evidence/<date>_m1/synthetic-quality.json` | 合成集质量报告（含 `root_sha256`） | `jcheng-dataset validate` |
| `evidence/<date>_m1/pusht-import.json` | 公开数据集导入报告（206 eps/25,650 frames） | `jcheng-dataset import` |
| `evidence/<date>_m1/so101-roundtrip.json` | 导入→导出→官方 loader 的一致性结果 | compat 作业 |
| `evidence/<date>_m1/anomaly-matrix.json` | 17 类异常的 check ID/退出码 | 测试脚本 |
| `evidence/<date>_m1/no-hardware.txt` | 静态扫描与“无机器人连接”声明 | `tests/test_no_hardware.py` |

证据只放摘要与哈希，不放数据集、图像或模型权重；数据与 LeRobot 输出都在
外部存储。

## 8. 风险清单

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | LeRobot 0.7 仍在快速演进，API/格式变动 | 中 | 适配器返工 | 硬 pin 0.7.0；原生层解耦；compat suite 作为升级门 |
| R2 | 6 GB 显存无法按官方示例微调 SmolVLA | 高 | M2 计划变更 | M2 先做显存 MVE；降 batch/冻结/LoRA；失败则改用 ACT |
| R3 | AV1 视频解码依赖系统 FFmpeg，CI 不可用 | 中 | 视频路径不可验收 | 默认 images 模式；`av` extra；inconclusive 不冒充通过 |
| R4 | ArmPi 状态是命令缓存，own-real 数据科学性不足 | 高 | 训练数据无效 | `state.truth` 强制；own-real 需总线读；报告 degraded |
| R5 | 异构相机频率导致大量丢帧/时间压缩 | 高 | 数据量减少/时间语义变化 | `strict` 默认；丢帧率阈值；sidecar 记录映射；M2 前复核 |
| R6 | 夹爪两套约定混用 | 中 | 动作符号错误 | 显式 `gripper.space`；DQ-J06/J07；映射必须显式 |
| R7 | LeRobot 需 Python 3.12，机器人 Humble 是 3.10 | 高 | M3 推理无法落机 | M3 设计时决定 laptop/容器/ONNX；M1 不承诺机器人端运行 |
| R8 | 公开数据集许可证/同意问题 | 低 | 不能入库/发布 | 只选 Apache-2.0/MIT；记录 license/revision；不重新分发 |
| R9 | 原生 PNG 存储体积大 | 中 | 磁盘压力 | 数据集在外部存储；M2 可加视频导出；249 GB 可用 |
| R10 | 数据契约未来变成跨仓库契约，产生漂移 | 中 | 多仓库不一致 | M1 不跨仓库；需要时先提案 interfaces + contract hash |

## 9. 需要用户决策的问题

| # | 问题 | 选项 | 推荐 |
|---|---|---|---|
| D1 | 是否接受“原生证据层 + LeRobot 训练层”双层模型？ | A 双层；B 只用 LeRobot + sidecar；C 只用原生 | A |
| D2 | ArmPi 动作向量是否采用 5 关节 + 1 夹爪（6 维），夹爪用 canonical 0…2.22？ | A 是；B 分开夹爪；C 用 raw `r_joint` | A |
| D3 | own-real 的 `state.truth` 若只有 `/joint_states`，是否允许入库但标 degraded？ | A 允许但禁止训练；B 直接拒绝；C 允许训练 | A |
| D4 | M1 公开数据集是否选 pusht（CI）+ svla_so101（验收）？ | A 是；B 只 pusht；C 另选 | A |
| D5 | 是否接受核心零 torch、LeRobot 仅 optional extra？ | A 是；B 核心就装 lerobot | A |
| D6 | M1 导出默认 images（PNG）还是 videos（MP4）？ | A images；B videos；C 两者都默认 | A |
| D7 | M1 是否现在就把 `jcheng.dataset.v1` 提案到 interfaces？ | A 暂不，M1 验收时再提；B 现在提 | A |

## 10. M1 完成 → M2 准入条件

M2（离线训练与评估）开始前必须全部满足：

1. **M1 验收通过**：`ACCEPTANCE.md` 英文记录 M1 全部标准，`evidence/`
   有对应报告，版本 `0.2.0` 已打 tag。
2. **至少一个 `pass` 数据集**：有明确 `source_class`、profile、`root_sha256`
   和 `result: pass` 的质量报告；不能只用 synthetic 作为唯一数据。
3. **LeRobot 兼容性有结论**：A4 为 Verified（laptop + `lerobot==0.7.0`）；
   若为 Inconclusive，M2 不得以 SmolVLA 为唯一训练目标。
4. **状态真值决策**：own-real 的 `state.truth` 已由操作员确认；若为
   `commanded`，M2 训练必须显式标注并在评估中降级解释。
5. **显存可行性**：M2 MVE-0 已测出 6 GB 卡上的可用 batch/step 时间；
   不通过则先改策略/冻结方案，不直接开训。
6. **评估协议预注册**：指标、留出 episode、阈值、失败判定写在
   `jcheng-benchmark` suite（或 learning `docs/EVAL.md`）并在训练前冻结。
7. **模型产物规则**：`/opt/jcheng/models/` 路径、SHA-256、policy card
   字段、禁止入库的检查已就绪。
8. **契约边界确认**：teleop/simulation 若要直接写 episode，interfaces
   提案已受理；否则 M2 仍只消费 M1 原生格式。

## 11. 本轮明确不做

- 不安装/训练/推理 SmolVLA；不下载模型权重。
- 不实现 Python 代码、不改 `ROADMAP.md`/`ACCEPTANCE.md`/`VERSION`。
- 不接触机器人、不启动 DDS、不调用 `ExecuteMotion`、不发布任何话题。
- 不修改 `jcheng-interfaces` 或其他仓库。
- 不把 `/tmp` 调研探针写入仓库或证据。

## 12. 实施偏差（2026-11-26，M1 实现后记录）

以下偏差是有意为之，已在 `ACCEPTANCE.md` 与证据中标注：

1. **JSON Schema 范围**：M1 只为质量报告提供 JSON Schema
   （`jcheng.dataset-quality-report.v1`）；dataset/episode/provenance/
   profile/action-map 由代码级校验器按 `04-DATA-CONTRACT.md` 执行。
   把这些契约变成独立 JSON Schema 是 M2 的 interfaces 提案项。
2. **`hold` 采样**：M1 只实现 `strict`；`--sample-policy hold` 会被拒绝，
   不进行隐式插值/保持。
3. **`import --format native`**：CLI 只实现 LeRobot v3 导入；历史记录若已
   符合 v1，可直接用 native reader/validator 检查。独立的历史格式适配器
   在操作员选定真实记录后再实现。
4. **视频模式**：M1 导出默认 `images`；`videos` 模式代码存在但未验收
   （U7），报告中必须保持 `inconclusive`。
5. **profile 数量**：生产 profile 仍是 4 个；`pusht_2d` 与 `probe_2d`
   只用于公开数据集/测试，不声称是 JCHENG 机器人。
