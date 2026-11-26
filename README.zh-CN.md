# jcheng-learning

**简体中文** | [English](README.md)

> 状态：**实验性**，2026-11-26。版本 0.2.0。
> M1 离线数据基础设施：仓库定义并校验数据契约，把公开 LeRobot v3 数据集
> 导入原生存储，并通过官方 LeRobot 写入器导出。仍然没有运行时节点、没有
> 策略、没有设备访问、没有运动权限。
> 本文为英文主文档的中文对照；如有歧义，以英文版为准。

`jcheng-learning` 是 JCHENG 生态的 L3 学习能力。职责是把录制的机器人 episode
变成版本化数据集，离线训练和评估策略，并且只在 M3 才向系统层发布技能**意图**。
它不驱动设备、不重建运动、不绕过 `jcheng-system`。

## 范围与边界

| 项 | 本仓库 |
|---|---|
| 层级 | L3 能力（`capability.yaml`） |
| 输入 | 操作员导出的 episode、公开 LeRobot v3 数据集、确定性合成数据 |
| 输出 | 不可变原生数据集（`jcheng.dataset.v1`）、质量报告、LeRobot v3 导出；M2 起还有模型产物 |
| 运动权限 | v0.2.0 无（`safety.class: offline`，运行时面为空） |
| 硬件访问 | `none` |
| 自有设备 | 无 |
| 禁止 | 设备访问、厂商话题、`/cmd_vel`、`/move_action`、`ExecuteMotion`、伪造传感器数据、数据集或模型权重入库 |

系统层是唯一运动起点；感知层是唯一 advisory 目标来源。学习策略可以提出动作，
但系统层会先应用控制租约、deadman、限位和停止锁存，之后才可能运动。

## M1 能力（v0.2.0）

- **数据契约**：`jcheng.dataset.v1` / `jcheng.episode.v1` /
  `jcheng.provenance.v1`；不可变 `dataset_id`、`SHA256SUMS`、每流时间戳、
  commanded/measured 分离、`source_class`（`synthetic / simulation /
  public-real / own-real`）。
- **机器人 profile**：ArmPi Ultra、Gate-2、Piper X、SO-101（仅导入），
  以及 PushT 2D 和探针 fixture。profile 是数据，不是代码分支。
- **校验器**：`DQ-*` 覆盖布局、哈希、时间、关节顺序、维度、单位、夹爪约定、
  限位、NaN/Inf、图像和 provenance；从不自动修复。
- **动作空间映射**：`action_map.py` 的逐维显式仿射规则，包含 ArmPi raw
  `r_joint` → canonical 夹爪映射；不隐式换序或换单位。
- **适配器**：只读 LeRobot v3 读取器（pyarrow，不需要 torch）、公开数据导入器、
  调用官方 `LeRobotDataset.create/add_frame/save_episode/finalize` 的导出器。
- **CLI**：`jcheng-dataset synth|inspect|validate|stats|report|import|convert|hash`，
  退出码固定为 `0/1/2/3/4`。
- **确定性合成数据**：相同 seed、固定 `created_at`、锁定依赖 → 相同
  `root_sha256`。

设计与冻结的数据契约见 [docs/m1/](docs/m1/00-INDEX.md)。M1 证据见
[evidence/20261126_m1/](evidence/20261126_m1/README.md)。

## 仓库布局

```text
jcheng-learning/
├── pyproject.toml                 # 包、console script、extra、pytest 配置
├── uv.lock                        # core/test/video/lerobot 的锁定解析
├── capability.yaml                # 准入清单（offline，hardware_access: none）
├── src/jcheng_learning/
│   ├── cli.py                     # jcheng-dataset
│   ├── native/                    # 原生读写
│   ├── lerobot/                   # v3 读取、导入、导出
│   ├── validate/                  # DQ-* 引擎与报告
│   ├── profiles/                  # robot-adapter.yaml + registry
│   └── schemas/                   # JSON Schema
├── tests/                         # 单元、CLI、原生、LeRobot 读取/导入测试
├── docs/
│   ├── ARCHITECTURE.md            # 数据、训练、推理平面
│   ├── DATA.md                    # 数据集布局、provenance、完整性规则
│   ├── INTEGRATION.md             # 准入、租约、失败语义
│   ├── m1/                        # M1 中文设计包
│   └── m2/                        # M2 计划与冻结评测协议
├── evidence/20261126_scaffold/    # M0 证据
├── evidence/20261126_m1/          # M1 离线证据
├── VERSION / CHANGELOG.md / ACCEPTANCE.md / ROADMAP.md
└── LICENSE-REVIEW.md
```

## 环境要求

- Python 3.12 与 `uv` 0.13.x（锁定环境）。
- 核心依赖：`PyYAML`、`pyarrow`、`numpy`、`Pillow`、`jsonschema`、
  `huggingface_hub`。核心路径不需要 ROS、torch 或 GPU。
- 可选 `video` extra：`av==15.1.0`，用于 AV1/MP4 解码。
- 可选 `lerobot` extra：`lerobot[dataset]==0.7.0`，用于官方写入器和兼容性
  oracle；它会拉 torch，核心 CI 不安装。
- 数据集和模型产物存放在仓库外。权重放 `/opt/jcheng/models/`；录制和数据集
  永不进 git。

## 快速开始

```bash
# 核心环境（无 torch）
uv sync --frozen --extra test

# 生成并校验确定性合成数据集
uv run jcheng-dataset synth --profile armpi_ultra --out /tmp/jcheng-m1 \
  --episodes 2 --frames 8 --fps 10 --seed 0 --image-size 64x48
uv run jcheng-dataset validate /tmp/jcheng-m1/synthetic-armpi_ultra-00000000

# 测试与门禁
uv run --frozen --extra test python -m pytest -q
bash scripts/check_repo_gate.sh
```

LeRobot 导出需要可选 extra：

```bash
uv sync --frozen --extra lerobot --extra video
uv run --extra lerobot jcheng-dataset convert /tmp/jcheng-m1/synthetic-armpi_ultra-00000000 \
  --to lerobot --out /tmp/jcheng-m1-export --mode images
```

操作员运行的兼容性套件在 [compat/](compat/README.md)。

## 验证状态

| 声明 | 状态 | 证据 |
|---|---|---|
| 仓库门禁与单元测试通过 | Verified（L0/L1，2026-11-26） | [evidence/20261126_m1/](evidence/20261126_m1/README.md) |
| M0 scaffold 与准入清单 | Verified（L0/L1，2026-11-26） | `evidence/20261126_scaffold/`；CI run 45733617970 |
| 原生数据集 schema、校验器与 CLI | Verified（L1，2026-11-26） | `evidence/20261126_m1/`；M1 验收时 65 个测试（当前 68 个，含 M2 harness） |
| 公开 LeRobot v3 导入与导出 | Verified（L1，2026-11-26） | pusht 206 eps/25,650 frames；SO-101 50 eps/11,939 frames；表格数据 round-trip 完全一致 |
| 确定性合成转换 | Verified（L1，2026-11-26） | 相同 `root_sha256`；图像像素差 0 |
| 17 类异常检测 | Verified（L1，2026-11-26） | `evidence/20261126_m1/anomaly-matrix.json` |
| 离线训练与评估 | Unverified | 未实现（M2） |
| 策略推理意图 | Unverified | 未实现（M3） |
| 硬件行为 | Unverified | 无 L5 会话；M1/M2 不接触机器人 |
| M2.0 排练 harness（不是策略） | Verified（L1，2026-11-26） | `evidence/20261126_m2-rehearsal/`；`evidence/20261126_m2-mve0/` |
| M2 多 seed 稳定性 + suite 提案 | Verified（L1，2026-11-26） | `evidence/20261126_m2-sweep/`；`docs/m2/BENCHMARK-PROPOSAL.md` |

完整报告：[ACCEPTANCE.md](ACCEPTANCE.md)。

## 相关仓库

- [`jcheng-interfaces`](https://github.com/JCHENG-Robotics/jcheng-interfaces) — 契约源与哈希。
- [`jcheng-system`](https://github.com/JCHENG-Robotics/jcheng-system) — 特权运行时；运动与硬件访问的唯一所有者。
- [`jcheng-perception`](https://github.com/JCHENG-Robotics/jcheng-perception) — M3 起消费的 advisory 感知目标。
- [`jcheng-simulation`](https://github.com/JCHENG-Robotics/jcheng-simulation) — 仿真 plant 与机器人目录参考。
- [`jcheng-teleop`](https://github.com/JCHENG-Robotics/jcheng-teleop) — 未来 episode 生产者。
- [`jcheng-benchmark`](https://github.com/JCHENG-Robotics/jcheng-benchmark) — M2 起的独立评测。
- [`jcheng-ops`](https://github.com/JCHENG-Robotics/jcheng-ops) — 无人值守健康与看门狗。
- [`.github`](https://github.com/JCHENG-Robotics/.github) — 生态路线图、变更日志、验收与仓库分类。

## 许可证

第三方与版权评审未完成；尚未添加 `LICENSE` 文件。数据集和模型产物有各自的
许可证，不受本仓库最终许可证覆盖。见 [LICENSE-REVIEW.md](LICENSE-REVIEW.md)。
