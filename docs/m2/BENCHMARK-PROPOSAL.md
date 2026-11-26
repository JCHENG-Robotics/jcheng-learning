# Benchmark suite 提案 — SmolVLA 离线动作误差

> 状态：**提案（2026-11-26）**。本文件只存在于 `jcheng-learning`，
> **没有修改 `jcheng-benchmark`**。正式 suite 由 benchmark 仓库 owner 评审后
> 落地；落地前不得声称“已通过 benchmark 验收”。

## 1. 为什么需要

M2 的 `jcheng.m2.eval.v1` 是 learning 侧的研发记录，不是正式验收。
按 2026-11-26 决策，正式验收必须由 `jcheng-benchmark` 用预注册 suite 执行。
本提案给出 suite 草案、样本格式和指标映射，供 benchmark 评审。

## 2. 指标映射

learning 侧每个留出帧输出一行 JSONL：

```json
{
  "schema": "jcheng.m2.eval.sample.v1",
  "sample_index": 0,
  "split": "held_out",
  "seed": 0,
  "steps": 50,
  "action_dim": 6,
  "action_mae_rad": 0.42,
  "action_rmse_rad": 0.55,
  "checkpoint_sha256": "sha256:...",
  "dataset_info_sha256": "sha256:..."
}
```

benchmark suite 使用 `kind: scalar`：

| Suite metric | source | aggregate | unit |
|---|---|---|---|
| `action_mae_rad` | `action_mae_rad` | `mean` | `rad` |
| `action_rmse_rad` | `action_rmse_rad` | `mean` | `rad` |

benchmark 还会给出 `count/p50/p95/max/min`；它们与 learning 的聚合口径一致
（逐帧、逐 chunk 步、逐维的均值）。

## 3. Suite 草案

- 排练（L1，synthetic）：
  [suites/m2-rehearsal-action-error-v1.yaml](suites/m2-rehearsal-action-error-v1.yaml)
- 正式（L4，recorded）：
  [suites/m2-action-error-v1.yaml](suites/m2-action-error-v1.yaml)

`thresholds` 目前为空：benchmark 会把空阈值 suite 判为 `inconclusive`，
这是正确的。正式阈值必须在**数据采集之前**写入 suite，并在 benchmark 的
`limitations`/commit message 中给出来源；不得在看到结果后补阈值。

## 4. 等级与数据来源

| Suite | level | data_source | 用途 |
|---|---|---|---|
| `m2-rehearsal-action-error-v1` | L1 | `synthetic` | 管线排练；永远不是策略/硬件证据 |
| `m2-action-error-v1` | L4 | `recorded` | 已录制 ArmPi 留出 episode 的正式离线评估 |

`L4` 不能用 synthetic 数据；`L1` 不能宣称硬件或闭环结果。这与
`jcheng-benchmark` 的 `BENCHMARK_PROTOCOL.md` 一致。

## 5. 交接步骤（待 benchmark 评审）

1. benchmark owner 在 `jcheng-benchmark/benchmarks/suites/` 添加 suite，
   保留本提案的 id 或说明改名。
2. learning 侧增加一个导出器，把 `jcheng.m2.eval.sample.v1` JSONL 写入
   外部数据集目录（不入 git）。
3. benchmark 用 `python -m jcheng_benchmark`（按该仓库 CLI）读取 JSONL，
   生成 report；报告记录 suite SHA-256、dataset SHA-256、checkpoint
   SHA-256、seed、host。
4. 只有 benchmark report 为 `pass` 才能在 M2 文档中写“benchmark verified”；
   learning 的 `eval.json` 仍然只是研发记录。

排练 suite 已用真实 benchmark harness 跑过 `seed0-samples.jsonl`：结果为
`inconclusive`（suite 无阈值，退出码 2），这是设计预期；报告在
`evidence/20261126_m2-sweep/benchmark-rehearsal-report.{json,md}`。

## 6. 未决问题

- 正式阈值取多少？必须先有 own-real 留出集和任务定义，不能凭合成数据定。
- 是否要求 per-joint 阈值？v1 只做整体 MAE/RMSE。
- 是否要求闭环成功率？M2 不要求；闭环留给 M4 受监督会话。
- 多 seed 是否各跑一个 suite？建议正式验收固定训练 seed，并附多 seed
  稳定性报告，不作为通过条件。
