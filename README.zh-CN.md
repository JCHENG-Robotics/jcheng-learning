# jcheng-learning

> 状态：**实验性**，2026-11-26。版本 0.1.0。
> 离线优先的骨架：本仓库定义数据集、训练与策略产物的边界，但不包含运行时节点、
> 不包含策略，也不访问硬件。运行中的机器人不会使用其中任何内容。
> 本文为英文主文档的中文对照；如有歧义，以 [README.md](README.md) 为准。

`jcheng-learning` 是 JCHENG 生态的 L3 学习能力。它的职责是把录制的机器人回合
转化为带版本的数据集，离线训练与评估策略，并且**仅从 M3 起**向系统层发布技能
**意图**，由系统层校验并执行。它绝不驱动设备、绝不自行重建运动，也绝不绕过
`jcheng-system`。

## 范围与边界

| 项 | 本仓库 |
|---|---|
| 层 | L3 能力（`capability.yaml`） |
| 输入 | 录制的回合与数据集清单，两者都存放在本仓库之外 |
| 输出 | 数据集清单与模型产物，两者都存放在本仓库之外；M3 起增加技能意图 |
| 运动授权 | v0.1.0 无（`safety.class: offline`，运行时表面为空） |
| 硬件访问 | `none` |
| 拥有的设备 | 无 |
| 禁止 | 设备访问、厂商话题、`/cmd_vel`、`/move_action`、`ExecuteMotion`、伪造传感器数据、把数据集或模型权重放进 git |

系统层是运动的唯一来源。感知层是建议目标的唯一来源。本仓库产出的策略可以提出
动作，但在任何东西移动之前，系统层会应用控制租约、deadman、限幅与停止锁存。

## 目录

```text
jcheng-learning/
├── capability.yaml                 # 准入清单（offline，hardware_access: none）
├── docs/
│   ├── ARCHITECTURE.md             # 数据、训练、推理三个平面
│   ├── DATA.md                     # 数据集布局、溯源与完整性规则
│   └── INTEGRATION.md              # 准入、租约与失败语义
├── tests/
│   ├── test_contract.py            # 清单与文档集检查
│   └── test_no_hardware.py         # 无硬件 / 无运动静态扫描
├── scripts/check_repo_gate.sh      # 仓库门禁（本地与 CI）
├── evidence/20261126_scaffold/     # M0 证据记录
├── VERSION
├── README.md / README.zh-CN.md
├── ROADMAP.md / CHANGELOG.md / ACCEPTANCE.md
└── LICENSE-REVIEW.md
```

## 依赖

- Python 3.10 或更新版本（CI 使用 3.12）、`pytest` 8.3.4、`PyYAML` 6.0.2。
- v0.1.0 不需要 ROS。只有 M3 出现推理节点时才需要 ROS 2 Humble。
- 数据集与模型产物的操作员侧存储，位于本仓库之外。权重文件放在
  `/opt/jcheng/models/`；录制数据与数据集绝不进入 git。
- 训练硬件（操作员笔记本 GPU）不属于本仓库，门禁也不依赖它。

## 快速开始

```bash
python3 -m pytest -q tests
bash scripts/check_repo_gate.sh
```

门禁检查文档集、准入清单、相对链接、密钥、模型权重、录制数据与两个测试模块。
它不接触机器人，也不打开任何设备。

## 验证状态

| 声明 | 状态 | 证据 |
|---|---|---|
| 仓库门禁与单元测试通过 | 已验证（L0/L1，2026-11-26） | `evidence/20261126_scaffold/`；[CI 运行](https://github.com/JCHENG-Robotics/jcheng-learning/actions/runs/45733617970) |
| 清单声明 `hardware_access: none` 且运行时表面为空 | 已验证（L0，2026-11-26） | `tests/test_contract.py` |
| 仓库中不存在硬件、厂商话题或运动调用 | 已验证（L0，2026-11-26） | `tests/test_no_hardware.py` |
| 数据集、训练或推理能力 | 未验证 | 尚未实现（M1–M3） |

完整报告：[ACCEPTANCE.md](ACCEPTANCE.md)。

## 相关仓库

- [`jcheng-interfaces`](https://github.com/JCHENG-Robotics/jcheng-interfaces) — 契约来源与契约哈希。
- [`jcheng-system`](https://github.com/JCHENG-Robotics/jcheng-system) — 特权运行时；运动与硬件访问的唯一所有者。
- [`jcheng-perception`](https://github.com/JCHENG-Robotics/jcheng-perception) — M3 起消费的建议感知目标。
- [`jcheng-ops`](https://github.com/JCHENG-Robotics/jcheng-ops) — 无人值守健康检查与看门狗。
- [`.github`](https://github.com/JCHENG-Robotics/.github) — 生态路线图、变更日志、验收与仓库分类。

## 许可证

第三方与版权审查尚未完成；尚未添加 `LICENSE` 文件。数据集与模型产物带有各自的
许可证，永不被本仓库的最终许可证覆盖。见 [LICENSE-REVIEW.md](LICENSE-REVIEW.md)。
