# M2 计划 — 离线训练与评估（排练阶段）

> 状态：**M2.0 排练 harness 已实现**（2026-11-26）。这不是 M2 完成，也不是
> 有效策略；正式训练仍以已接受的数据集和预注册评测为前提。
> 本目录是 `docs/` 下的中文设计/协议材料；根文档保持英文。

## 0. 训练宿主决定（2026-11-26）

- **M2 训练继续在 RTX 3060 Laptop 6 GB 上进行。**
- **AGX Orin 64 GB 只做推理/感知宿主，不参与 M2 训练。**
- 原因：Orin 的 conda `lerobot` 环境是 0.4.4 / Python 3.10 / torch 2.8，
  与 M2 锁定的 LeRobot 0.7.0 / Python 3.12 不同；当前 GPU 又被 SAM3
  稳定性任务占满（99% / 76°C），训练会争抢算力并影响 SAM3。
- 2026-11-26 只读探测确认 Orin 输入为 18.984/19.000 V，19V 电源前提已满足；
  但这不改变“不用于训练”的决定。

## 1. 已确认的三项决策（2026-11-26）

| 决策 | 选择 |
|---|---|
| M2 第一个训练/评估对象 | **合成 ArmPi 管线排练**；不声称策略有效，等 own-real 数据再替换 |
| own-real 的 `state.truth` | **必须 `bus_read` measured**；命令缓存数据只用于格式测试，不用于训练 |
| 评测协议 | **learning 预注册 + `jcheng-benchmark` 正式验收**；训练指标不作为验收 |

## 2. M2.0 范围（已实现）

1. `jcheng-train rehearsal`：包装官方 `lerobot-train`，固定 seed、batch、steps，
   记录命令、版本、数据集哈希、checkpoint 文件哈希与训练日志。
2. `jcheng-eval`：teacher-forced 离线动作误差评估，输出
   `jcheng.m2.eval.v1` JSON。
3. Policy card：记录 base model、数据集、训练参数、checkpoint 哈希、评估结果、
   限制与“无硬件”声明；权重放 `/opt/jcheng/models/`，不入 git。
4. 证据：`evidence/20261126_m2-rehearsal/`。

不在 M2.0 范围：

- 正式训练收敛、超参搜索、策略质量声明。
- 实机推理、`ExecuteMotion`、DDS、lease 或任何运动路径。
- 修改 `jcheng-benchmark`；正式 benchmark suite 在策略进入验收时再提案。

## 3. 训练配置（排练）

| 项 | 值 |
|---|---|
| 数据 | 合成 ArmPi：train 3 eps / 240 frames；val 1 ep / 80 frames；2 相机；64×48 |
| Policy | `lerobot/smolvla_base`（450M，Apache-2.0） |
| Batch / optimizer updates | 8 / 20 |
| Seed | 0 |
| `empty_cameras` | 1（2 相机 → camera1/2 + 空相机） |
| 设备 | RTX 3060 Laptop 6 GB；torch 2.15.0+cu132；lerobot 0.7.0 |
| 峰值显存 | 3.53 GB（MVE-0 batch 8 为 3.14 GB；训练步含优化器状态） |
| 权重路径 | `/opt/jcheng/models/m2-rehearsal-20261126/` |

## 4. M2.0 结果

- 20 步训练完成；loss 4.972 → 1.199；20 步约 11 s（不含模型加载）。
- checkpoint `checkpoints/000020/pretrained_model`，10 个文件已哈希；
  `model.safetensors` = `sha256:14dee4d174de35a97e33f3c8832b1ed0b42e4e1d9a3059680386bcc2d6d633cb`。
- 留出 episode 的 teacher-forced 动作误差：MAE `0.4841` rad、
  RMSE `0.6379` rad（10 个样本 × 50 步 × 6 维）；这是排练指标，
  **不是成功率，也不是可用策略证据**。
- 有效 batch 64：`batch 8 × grad_accum 8`，20 次 optimizer 更新 =
  160 个 micro-batch；峰值 3.75 GB，总墙钟 105.9 s（含加载），
  MAE `0.4948` / RMSE `0.6520`。6 GB 可以逼近 batch 64，但没有速度收益；
  记录见 [evidence/20261126_m2-gradaccum/](../../evidence/20261126_m2-gradaccum/README.md)。
- 完整记录见 [evidence/20261126_m2-rehearsal/](../../evidence/20261126_m2-rehearsal/README.md)。

多 seed 稳定性（同一 train/val 数据，seed 0/1/2，固定评估 seed 0）：

| 指标 | 均值 ± 总体标准差 |
|---|---|
| `action_mae` | 0.4917 ± 0.0129 rad |
| `action_rmse`（逐帧 RMSE 的均值） | 0.6513 ± 0.0226 rad |
| final loss | 1.254 ± 0.041 |

seed 0 重跑得到相同的 `model.safetensors` 哈希与相同评估指标。记录见
[evidence/20261126_m2-sweep/](../../evidence/20261126_m2-sweep/README.md)。

## 5. M2 正式退出条件（尚未满足）

1. 使用一个已接受的数据集（`result: pass` 或经批准的 `inconclusive`），
   记录 `dataset_id` / `root_sha256` / `source_class`。
2. 训练可复现：固定 seed、batch、steps、依赖版本；重新运行产生相同
   train-record 结构（允许时间戳/耗时不同）。
3. checkpoint 与 policy card 有哈希；权重在 `/opt/jcheng/models/`，不入 git。
4. 评测协议已预注册（[EVAL.md](EVAL.md)），并在 `jcheng-benchmark` 中以同一
   指标定义做正式验收；learning 的 JSON 不是正式验收。
5. own-real 数据若进入训练，必须 `truth_source=bus_read`；否则拒绝。
6. 无任何硬件运动路径；M4 之前不做硬件有效性声明。

## 6. 风险

| 风险 | 影响 | 处理 |
|---|---|---|
| 合成数据没有科学价值 | 排练指标不可外推 | 只作为管线证据；政策/模型卡标 `rehearsal-only` |
| 6 GB 批量边界未二分 | 真实数据可能 OOM | 以 batch 8 起步；必要时梯度累积 |
| 评测是 teacher-forced | 不能代表闭环 | 正式验收交给 benchmark / M4 监督会话 |
| 训练数据未定 | M2 无法进入正式阶段 | 先接受 own-real 数据并确认 `bus_read` |
| 评测后调参 | 指标不可信 | 协议冻结；变更需新协议版本并记录 |
