# M2 评测协议（预注册）

> 状态：**冻结 v1，2026-11-26**。在任何 M2 正式训练之前注册；训练后看到的
> 指标不得改变本协议。变更必须新建 `v2` 并记录原因。
> 本协议不授权硬件、实机推理或运动。

## 1. 目标与边界

- 本协议评估**离线策略的动作预测误差**，不评估闭环成功率、安全性或硬件行为。
- 正式验收由 `jcheng-benchmark` 以其 suite 机制执行；learning 的
  `jcheng.m2.eval.v1` 报告是训练/研发记录，不是验收结论。
- 不使用训练集帧做评估；训练/留出 episode 必须按 `dataset_id` 和 episode
  列表显式分离。

## 2. 数据划分

| 项 | 规则 |
|---|---|
| 训练集 | 显式 episode 列表；记录 `dataset_id` 与 `root_sha256` |
| 留出集 | 至少 1 个完整 episode，不得与训练集重叠 |
| 划分冻结 | 训练开始前写入 train-record；训练后不得改划分 |
| own-real | 只接受 `state.truth_source=bus_read`；命令缓存数据不进入训练/评估 |
| 来源类别 | 报告必须写 `synthetic / simulation / public-real / own-real`，不得混写 |

## 3. 指标（v1）

| ID | 定义 | 单位 | 聚合 |
|---|---|---|---|
| `action_mae` | 预测动作与记录动作的绝对误差 | rad（按维度单位） | 所有样本、chunk 步、维度的均值 |
| `action_rmse` | 逐帧 RMSE 的均值（不是全局 RMSE） | rad | 先算每帧 RMSE，再对帧取 mean |
| `per_dim_mae` | 每个动作维度的 MAE | rad | 按维度 |
| `n_samples` | 参与评估的帧数 | 帧 | 计数 |
| `chunk_size` | 策略一次预测的步数 | 步 | 固定 50（SmolVLA 默认） |

规则：

- 预测和真值都必须是**绝对关节位置**（`joint_position_absolute`）；不做
  隐式相对/差分转换。
- 比较前必须使用与训练相同的 pre/post processor；报告记录 checkpoint 哈希。
- 评估推理 seed 固定（默认 0）；同一 checkpoint + 同一 seed 必须可复现。
  不同训练 seed 报告分布，不把最好 seed 当作结果。
- 训练记录必须同时写 `micro_steps` 与 `optimizer_steps`。LeRobot 的
  `--steps` 是 micro-batch 数；`grad_accum=8` 时 20 次更新需要 160 个
  micro-batch，不能把 20 个 micro-batch 写成“20 步”。
- NaN/Inf、维度不符、缺失图像或 checkpoint 哈希不符 → 评估失败，不产生指标。
- 不使用“平均误差很小”替代逐值检查；失败样本不得静默丢弃。

## 4. 通过/失败语义（M2）

M2.0 排练（合成数据）只要求：

1. 训练命令、依赖版本、数据哈希、seed、batch、steps 完整记录；
2. checkpoint 与 policy card 有 SHA-256；
3. 评估 JSON 符合 `jcheng.m2.eval.v1`，且无 NaN/Inf/维度错误；
4. 明确标注“rehearsal-only，不是有效策略”。

M2 正式训练（真实数据）还需：

1. 训练/留出划分在训练前冻结；
2. `jcheng-benchmark` suite 使用同一 `action_mae`/`action_rmse` 定义；
3. 阈值在 suite 中预注册；未达阈值即失败，不因“看起来还行”改阈值；
4. own-real 只用 `bus_read` measured；
5. 任何硬件声明留到 M4，单独授权。

## 5. 报告与证据

- learning 侧：`jcheng.m2.eval.v1` JSON + policy card + train-record。
- benchmark 侧：suite YAML + JSONL 样本 + report；两者都记录数据集
  `root_sha256`、checkpoint 哈希、seed、依赖版本。
- 报告不得包含数据集、图像或权重；只放指标、哈希与限制。

## 6. 非目标

- 闭环成功率、抓取成功率、恢复能力。
- 安全性、e-stop、碰撞、力矩或硬件寿命。
- 跨机器人/跨动作空间的零样本迁移。
- 用训练 loss 代替验收指标。
