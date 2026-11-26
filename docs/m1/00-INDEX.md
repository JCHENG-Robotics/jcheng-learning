# jcheng-learning M1 设计评审包

> 状态：**设计已批准，M1 已实现**（v0.2.0，2026-11-26）。本目录是设计参考
> 材料；实际实现与证据见
> [evidence/20261126_m1/](../../evidence/20261126_m1/README.md) 与
> [ACCEPTANCE.md](../../ACCEPTANCE.md)。根文档 `README.md`、`ROADMAP.md`、
> `CHANGELOG.md`、`ACCEPTANCE.md` 保持英文；本目录按用户要求使用中文，仅作为
> `docs/` 下的设计参考材料（`.github/docs/documentation-standard.md` §3 允许
> `docs/` 保留中文材料）。
>
> 本轮范围：只读审查、一手源码调研、技术设计。**不修改实现代码，不训练模型，
> 不接触机器人，不产生任何运动路径。**

## 1. 文件索引

| 文件 | 内容 | 对应交付项 |
|---|---|---|
| [01-GAP-ANALYSIS.md](01-GAP-ANALYSIS.md) | 仓库现状、M1 缺口、跨仓库边界事实 | 交付 1 |
| [02-LEROBOT-RESEARCH.md](02-LEROBOT-RESEARCH.md) | LeRobot v0.7.0 / SmolVLA 一手调研与可复现实验 | 交付 2 |
| [03-DESIGN.md](03-DESIGN.md) | M1 架构、模块、依赖、实施计划、测试矩阵、风险、M2 准入 | 交付 3、5、6、7、8、9 |
| [04-DATA-CONTRACT.md](04-DATA-CONTRACT.md) | 数据契约、Robot Profile、Action Space Mapping、跨仓库接口边界 | 交付 4 |

## 2. 一句话结论

M1 应采用**双层数据模型**：仓库内定义的、不可变的 **JCHENG 原生 episode 存储
（`jcheng.dataset.v1`）** 作为审计、校验和溯源的唯一事实来源；**LeRobot
Dataset v3.0** 作为唯一的训练交换格式，由适配器单向导出，绝不复制或重写
LeRobot 的 Parquet/MP4/训练基础设施。原生格式只负责“证据”，LeRobot 负责
“训练”。

## 3. 审批时需要拍板的 7 件事

| # | 决策 | 推荐选项 | 影响 |
|---|---|---|---|
| D1 | 数据模型 | 原生证据层 + LeRobot 训练层（双层） | 决定 M1 全部模块边界 |
| D2 | 动作空间 | 每个机器人一个 `joint_position_absolute` 空间；ArmPi 动作向量为 5 关节 + 1 夹爪（6 维）；夹爪采用系统层 canonical `0.0 闭合 … 2.22 张开` | 决定数据集维度、归一化与未来策略头 |
| D3 | 原生状态的“真值” | `state.truth` 必须显式声明 `measured / commanded`；ArmPi 若用 `/joint_states` 就是 `commanded`，报告标 `degraded` | 决定 own-real 数据能否用于 M2 训练 |
| D4 | M1 公开数据集 | CI 用 `lerobot/pusht`（MIT，7.7 MB，206 eps）；验收用 `lerobot/svla_so101_pickplace`（Apache-2.0，86 MB，50 eps，真机 SO-101） | 决定网络/磁盘/许可证证据 |
| D5 | 依赖策略 | 核心 `pyarrow/Pillow/numpy/PyYAML/jsonschema/huggingface_hub`；`lerobot[dataset]==0.7.0` 只进可选 extra，核心 CI 不装 torch | 决定 CI 时长与可复现性 |
| D6 | 导出默认 | M1 默认 `images`（PNG，逐像素可核验），`videos` 仅作为 M2 规模选项；采样默认 `strict`（丢弃不齐帧，不插值） | 决定“转换前后一致性”的可证明性 |
| D7 | 契约归属 | M1 不 bump `jcheng-interfaces`；`jcheng.dataset.v1` 先留在 learning；若 teleop/simulation 要写它，M1 验收时提交 interfaces 契约提案 | 决定是否触发跨仓库契约变更 |

## 4. 与现有路线图的关系

仓库现有 `ROADMAP.md` 把 M1 定义为“dataset manifest and integrity gate”。本轮
用户要求把 M1 扩展为 7 个工作包（Schema、Adapter、Validator、Action Space
Mapping、Provenance、Offline Pipeline、CLI）。本设计**重基线** M1 的范围，
但不改变 M2（离线训练与评估）、M3（策略意图节点）、M4（受监督硬件验收）的
含义。审批通过后，实现阶段才会更新英文 `ROADMAP.md` / `ACCEPTANCE.md` /
`CHANGELOG.md` 并把版本从 `0.1.0` 升到 `0.2.0`；本轮不改。

## 5. 已核实的事实（摘要）

- 当前 M0 基线：`python3 -m pytest -q tests` → 13 passed；
  `bash scripts/check_repo_gate.sh` → OK（2026-11-26 本机复跑）。
- LeRobot 最新稳定版 **0.7.0**，Apache-2.0，`requires-python >=3.12`，
  `torch>=2.7,<2.16`，`numpy>=2.0,<2.3`；Dataset 格式为 **v3.0**，主版本
  不兼容旧版（v2.1 不能直接被 v0.7.0 读取）。
- `smolvla_base` 的 `config.json`：6 维 state / 6 维 action、3 路相机
  （`camera1..3`）、`chunk_size=50`、`n_action_steps=50`、`max_*_dim=32`、
  `MEAN_STD` 归一化、SmolVLM2-500M 骨干。
- 本机：Python 3.12.3、RTX 3060 Laptop 6 GB、无 torch/lerobot、无 HF 缓存、
  249 GB 可用磁盘；网络可达 GitHub / Hugging Face / PyPI。
- 机器人侧：Humble + Python 3.10，**不能直接安装 LeRobot 0.7**；M3 推理节点
  的运行位置必须另行设计（详见 03-DESIGN.md §9 风险 R7）。
- U1/U2 探针（2026-11-26，`/tmp`）：PyAV 15.1.0 可解码 so101 的 AV1 视频
  （libdav1d，640×480，11,939 帧）；`lerobot[dataset]==0.7.0` + CPU torch 可完成
  图像模式写入并被官方 loader 读回。**图像模式最终无 `images/` 目录，图像字节
  嵌在 Parquet 中**，一致性检查须从 Parquet 解码。

## 6. 评审建议顺序

1. 先读 [01-GAP-ANALYSIS.md](01-GAP-ANALYSIS.md) §4–§6，确认边界事实没有偏差。
2. 再读 [04-DATA-CONTRACT.md](04-DATA-CONTRACT.md) §2–§4，确认数据模型与动作空间。
3. 然后读 [03-DESIGN.md](03-DESIGN.md) §3–§7，确认模块、依赖与测试矩阵。
4. 最后看 [02-LEROBOT-RESEARCH.md](02-LEROBOT-RESEARCH.md) 的来源清单与
   “未决验证项”，确认没有把未验证假设写进设计。

## 7. 明确不在本轮范围

- 不安装 LeRobot、不创建 venv、不下载数据集、不写实现代码（调研阶段的临时
  `/tmp` 探针不计入仓库）。
- 不做 SmolVLA 训练或推理，不做实机策略执行。
- 不修改 `jcheng-interfaces` 或其他仓库。
- 不产生 `evidence/` 下的验收声明；M1 证据在实现阶段生成。
