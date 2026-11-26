# 02 — LeRobot / SmolVLA 技术调研（一手来源）

> 状态：提案（2026-11-26）。所有结论来自以下三类材料之一：固定版本的源码、
> 官方文档、或本次可复现实验。未经验证的推断在 §10 单独列出。
>
> 固定基线：**LeRobot `v0.7.0`，tag commit `410c095eacc0011d998a73383eb94abed2715af0`**
> （本地浅克隆，2026-11-26 核对）。本文引用的行号均指该 commit。

## 1. 调研方法与可复现记录

| 实验 | 命令/来源 | 结果 |
|---|---|---|
| 版本与 Python 要求 | `https://pypi.org/pypi/lerobot/json` | `0.7.0`；`requires_python >=3.12` |
| 源码基线 | `git clone --depth 1 --branch v0.7.0 https://github.com/huggingface/lerobot` | 33 MB；HEAD `410c095` |
| 真实 v3 数据 | 下载 `lerobot/pusht` 的 `meta/*` 与 `data/chunk-000/file-000.parquet`（7.7 MB） | 206 eps / 25,650 frames / 10 fps / 2 维 |
| 真实真机数据元信息 | `lerobot/svla_so101_pickplace/meta/info.json` | 50 eps / 11,939 frames / 30 fps / 6 维 / 2 相机 |
| 模型配置 | `lerobot/smolvla_base/config.json` | 6 维 state/action、3 相机、chunk 50、`max_*_dim=32` |
| 论文 | `https://arxiv.org/abs/2506.01844` | 2025-06-02；单 GPU 训练、异步推理 |
| 仓库基线 | `pytest -q tests`；`scripts/check_repo_gate.sh` | 13 passed；gate OK |
| U1 AV1 解码 | 下载 `svla_so101_pickplace` 的 `observation.images.up` 视频（39 MB），PyAV 15.1.0 解码 | 流 `libdav1d`，640×480，11,939 帧（与 `total_frames` 一致），首帧 `uint8(480,640,3)` |
| U2 LeRobot 图像写入 | `uv` 安装 `lerobot[dataset]==0.7.0` + `torch==2.15.0+cpu`；`LeRobotDataset.create(use_videos=False)` 写 2 eps/8 frames，再加载 | 成功；state/action 逐值相等；最终目录只有 `meta/`+`data/*.parquet`，**没有 `images/`** |

`pusht` 的 Parquet 实测 schema（`pyarrow 21.0.0` 读取）：

```text
data/chunk-000/file-000.parquet  (25,650 rows)
observation.state: fixed_size_list<float>[2]
action:            fixed_size_list<float>[2]
episode_index: int64      frame_index: int64      timestamp: float
next.reward: float        next.done: bool         next.success: bool
index: int64              task_index: int64
```

`meta/episodes/chunk-000/file-000.parquet`（206 行）实测列：

```text
episode_index, data/chunk_index, data/file_index,
dataset_from_index, dataset_to_index,
videos/<key>/chunk_index, videos/<key>/file_index,
videos/<key>/from_timestamp, videos/<key>/to_timestamp,
tasks, length,
stats/<feature>/{min,max,mean,std,count},
meta/episodes/chunk_index, meta/episodes/file_index
```

## 2. 版本、许可与依赖

| 项 | 值 | 来源 |
|---|---|---|
| 版本 | `0.7.0`（当前最新稳定版） | PyPI JSON |
| 许可证 | Apache-2.0 | `pyproject.toml` `license`；仓库 `LICENSE` |
| Python | `>=3.12` | `pyproject.toml` 第 32 行 |
| torch / torchvision | `>=2.7,<2.16` / `>=0.22,<0.30` | `pyproject.toml` 第 62–63 行 |
| numpy | `>=2.0,<2.3` | `pyproject.toml` 第 64 行 |
| pyarrow | `>=21,<30`（`[dataset]` extra） | `pyproject.toml` 第 108–112 行 |
| PyAV | `>=15,<16`（`av-dep`） | `pyproject.toml` 第 153 行 |
| transformers（SmolVLA） | `>=5.22,<5.23` | `pyproject.toml` `transformers-dep` |
| 数据集格式版本 | `CODEBASE_VERSION = "v3.0"` | `src/lerobot/datasets/dataset_metadata.py` 第 64 行 |

设计含义：

- LeRobot 是**重依赖**（torch 是硬依赖）。不能让 `jcheng-learning` 的核心
  CLI 在没有 torch 的环境里无法运行。
- LeRobot 0.7 要求 Python ≥3.12；机器人侧 Humble 是 Python 3.10，
  **M3 推理节点不能直接跑在机器人系统 Python 上**。
- numpy 必须 `<2.3`；本机系统 numpy 是 1.26.4，必须用独立 venv。

## 3. LeRobot Dataset v3.0 格式

官方文档：`docs/source/lerobot-dataset-v3.mdx`。核心设计（第 55–87 行）：

1. **表格数据**：低维高频信号（state/action/timestamp）存 **Parquet**；
2. **视觉数据**：同一 episode 的帧拼接编码为 **MP4**，按相机分片；
3. **元数据**：`meta/info.json`（schema、fps、路径模板）、
   `meta/stats.json`（归一化统计）、`meta/tasks.parquet`（任务文本→ID）、
   `meta/episodes/*.parquet`（每 episode 的长度、偏移、任务、统计）。

目录（简化）：

```text
<dataset>/
├── meta/info.json
├── meta/stats.json
├── meta/tasks.parquet
├── meta/episodes/chunk-000/file-000.parquet
├── data/chunk-000/file-000.parquet
├── videos/<video_key>/chunk-000/file-000.mp4
└── (use_videos=False) 图像字节嵌入 data/*.parquet；
    写入时的临时 images/<image_key>/... 在 save_episode 后删除
```

### 3.1 `info.json`

`DatasetInfo` 数据类（`src/lerobot/datasets/utils.py` 第 180–230 行）字段：

```text
codebase_version, fps, features,
total_episodes, total_frames, total_tasks,
chunks_size, data_files_size_in_mb, video_files_size_in_mb,
data_path, video_path, storage_format,
robot_type, splits, tools
```

`features` 每项至少含 `dtype`、`shape`、`names`：

- 标量/向量：`{"dtype": "float32", "shape": [D], "names": [...]}`；
- 图像/视频：`{"dtype": "video"|"image", "shape": [H, W, 3], "names": ["height","width","channels"], "info": {...}}`；
- 默认列（`src/lerobot/utils/constants.py` 第 109–115 行）：
  `timestamp`、`frame_index`、`episode_index`、`index`、`task_index`。

`info.json` 的解析对未知字段只记 warning 并丢弃
（`DatasetInfo.from_dict`，`utils.py` 第 260–270 行），因此 **JCHENG 的
provenance 不能写进 `info.json`**，必须放 sidecar。

### 3.2 `stats.json` 与 episode 统计

`compute_stats.py` 输出的键：`min/max/mean/std/count`，以及
`q01/q10/q50/q90/q99`。`meta/episodes/*.parquet` 只保留
`min/max/mean/std/count`（实测列见 §1）。这些统计是训练归一化的来源；
`MEAN_STD` 的 state/action 归一化直接依赖它们。

### 3.3 真实数据集的差异

| 数据集 | 机器人 | 维度 | 相机 key | fps | 许可 |
|---|---|---|---|---|---|
| `lerobot/pusht` | unknown（公开仿真基准） | state/action 2 | `observation.image`（单数） | 10 | MIT |
| `lerobot/svla_so101_pickplace` | `so100_follower`（真机 SO-101） | 6 | `observation.images.up` / `.side` | 30 | Apache-2.0 |
| `lerobot/svla_so100_pickplace` | `so100`（真机 SO-100） | 6 | `observation.images.top` / `.wrist` | 30 | Apache-2.0 |

设计含义：相机 key 是自由命名（`observation.image` 与
`observation.images.<name>` 都存在），适配器必须显式映射到策略期望的 key，
不能假设固定名字。

## 4. 写入 API（exporter 必须使用）

`LeRobotDataset.create`（`src/lerobot/datasets/lerobot_dataset.py` 第 767 行；
需要安装 `lerobot[dataset]==0.7.0`，因为 `lerobot.datasets` 会导入 `datasets`/`pyarrow`）：

```python
LeRobotDataset.create(
    repo_id: str,
    fps: int,
    features: dict,
    root: str | Path | None = None,
    robot_type: str | None = None,
    use_videos: bool = True,
    tolerance_s: float = 1e-4,
    ...
)
```

写入流程（官方文档第 321–350 行；源码第 500–567 行）：

```python
dataset = LeRobotDataset.create(...)
dataset.add_frame(frame)     # 每帧必须含 "task" 键（docstring 第 508 行）
dataset.save_episode()
dataset.finalize()           # 必须调用，否则 Parquet footer 不完整
```

关键约束：

| 约束 | 源码/文档 | 对 exporter 的影响 |
|---|---|---|
| `add_frame` 必须含 `task` | `lerobot_dataset.py` 第 500–513 行 | 原生 episode 的 task 必须逐帧传入 |
| `use_videos=False` 时 features 不得含 `dtype: video` | `dataset_metadata.py` 第 860–864 行 | 图像模式必须用 `dtype: image` |
| `root` 目录必须不存在 | `dataset_metadata.py` 第 842 行 `exist_ok=False` | 先写临时目录再原子重命名 |
| `fps` 为整数 | `DatasetInfo.__post_init__` 第 235–241 行 | 原生 fps 必须是整数 |
| 特征名不得含 `/` | `utils/feature_utils.py` 第 34–45 行 | 相机 key 用 `observation.images.<name>` |
| `finalize()` 必须调用 | 文档第 321–350 行 | 导出结束强制校验 `meta/info.json` |

`use_videos=False` 时，写入器先把每帧写到
`images/{image_key}/episode-{episode_index:06d}/frame-{frame_index:06d}.png`
（`datasets/utils.py` 第 178 行 `DEFAULT_IMAGE_PATH`），随后
`embed_images()` 把图像字节嵌入 Parquet，并在 `save_episode()` 结束时删除
临时目录（`dataset_writer.py` 第 393 行 `_delete_camera_frame_dirs`）。
**最终数据集没有 `images/` 目录**；逐像素核验必须从 Parquet 的嵌入图像解码，
不能假设 PNG 文件仍在。U2 实测确认了这一点。

## 5. 读取与训练入口

### 5.1 `LeRobotDataset`

```python
dataset = LeRobotDataset(repo_id_or_path, delta_timestamps={...})
sample = dataset[100]
# {'observation.state': tensor, 'action': tensor,
#  'observation.images.<cam>': tensor, 'timestamp': tensor, ...}
```

`delta_timestamps` 按秒展开时间窗（文档第 112–121 行）。SmolVLA 的
`observation_delta_indices = [0]`、`action_delta_indices = range(chunk_size)`
（`configuration_smolvla.py` 第 154–159 行），训练时由
`resolve_delta_timestamps` 转成每帧的 delta（`datasets/factory.py` 第 40–100 行）。

### 5.2 `lerobot-train`

```bash
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=<repo> \
  --rename_map='{"observation.images.top": "observation.images.camera1", ...}' \
  --batch_size=64 --steps=20000 --policy.device=cuda
```

- `--policy.path` 载入预训练 checkpoint；`--policy.type` 从零训练。
- `rename_map` 只重命名 **observation** key（图像/state），不动 action；
  且要求 `pretrained_path` 存在（`configs/train.py` 第 322 行）。
- `DatasetConfig` 含 `eval_split`（按 task 留出比例，`configs/default.py` 第 79 行），
  但正式评测仍应走 `jcheng-benchmark`。

### 5.3 `empty_cameras`

`SmolVLAConfig.empty_cameras: int = 0`（`configuration_smolvla.py` 第 49 行）。
文档 `rename_map.mdx` 说明：数据集相机数少于策略期望时，用
`empty_cameras=N` 添加被 mask 的空相机，而不是改模型结构。设计含义：
ArmPi 只有 2 路相机时，可以微调 3 相机的 `smolvla_base`，无需伪造第三路图像。

### 5.4 评估入口

- `lerobot-eval`：在仿真环境（如 pusht/libero）里跑 rollout，算成功率；
- `lerobot-rollout`：真机部署策略（M3/M4 才会涉及）。

M1 不使用这两个入口；M2 的离线评估应先用留出 episode 的动作误差/轨迹误差，
正式成功率验收交给 `jcheng-benchmark`。

## 6. SmolVLA

### 6.1 模型与训练配置

`smolvla_base/config.json` 实测：

```json
{
  "type": "smolvla",
  "input_features": {
    "observation.state": {"type": "STATE", "shape": [6]},
    "observation.images.camera1": {"type": "VISUAL", "shape": [3,256,256]},
    "observation.images.camera2": {"type": "VISUAL", "shape": [3,256,256]},
    "observation.images.camera3": {"type": "VISUAL", "shape": [3,256,256]}
  },
  "output_features": {"action": {"type": "ACTION", "shape": [6]}},
  "chunk_size": 50,
  "n_action_steps": 50,
  "max_state_dim": 32,
  "max_action_dim": 32,
  "normalization_mapping": {"VISUAL": "IDENTITY", "STATE": "MEAN_STD", "ACTION": "MEAN_STD"},
  "vlm_model_name": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
  "num_steps": 10,
  "freeze_vision_encoder": true,
  "train_expert_only": true
}
```

`SmolVLAConfig`（`configuration_smolvla.py` 第 27–101 行）默认值：

| 字段 | 默认 | 含义 |
|---|---|---|
| `n_obs_steps` | 1 | 单帧观测 |
| `chunk_size` / `n_action_steps` | 50 / 50 | 一次预测 50 步动作块 |
| `max_state_dim` / `max_action_dim` | 32 / 32 | 短向量补零到 32 维 |
| `resize_imgs_with_padding` | (512, 512) | 图像等比缩放 + padding |
| `empty_cameras` | 0 | 可补空相机 |
| `normalization_mapping` | STATE/ACTION `MEAN_STD` | 依赖 `stats.json` |
| `num_steps` | 10 | flow matching 去噪步数 |
| `freeze_vision_encoder` / `train_expert_only` | true / true | 默认只训 action expert |

论文（arXiv:2506.01844，2025-06-02）主张：小模型、单 GPU 训练、消费级 GPU/CPU
部署、异步推理；官方文档称 20k steps 在单张 A100 上约 4 小时，并建议约
50 个 episode 起步（`docs/source/smolvla.mdx` 第 60–90 行）。

### 6.2 动作输出

- `select_action` 维护动作队列，队列空时调用 `predict_action_chunk`，
  返回形状 `(batch, n_action_steps, action_dim)`，再逐步出队
  （`modeling_smolvla.py` 第 256–285 行）。
- `prepare_state` / `prepare_action` 用 `pad_vector` 补到 32 维
  （第 462–470 行），loss 只取前 `max_action_dim`（第 334 行）。
- action 是**连续向量**，训练目标是 flow matching；不是离散 token。

### 6.3 与 ArmPi 的关系

- ArmPi 的 5 关节 + 1 夹爪恰好是 6 维，与 `smolvla_base` 的 6 维**维度相同**，
  但关节语义、零位、方向、限位、夹爪约定完全不同；**维度相同不等于动作空间
  兼容**。不能零样本迁移。
- Piper X 是 7 维（6 关节 + prismatic 夹爪），与 6 维 checkpoint 的输出头
  形状不一致；M2 若要支持，必须新建 action head 并重新训练，不能复用原头。
- `max_*_dim=32` 的补零只是网络内部对齐，不是跨机器人共享权重的理由。

## 7. 动作表示

`docs/source/action_representations.mdx` 定义三种表示：

| 表示 | 定义 | 备注 |
|---|---|---|
| Absolute | 直接给目标位置 | LeRobot 默认；需要一致坐标/零位 |
| Relative | 相对“预测时刻的当前 state” | OpenPI/pi0 系列；每个 chunk 共享同一参考点 |
| Delta | 相对上一条动作 | 误差会累积；UMI 明确反对 |

LeRobot 的处理器链（文档第 203–225 行）：

```text
raw absolute joint actions → relative → normalize → model
model output → unnormalize → absolute → robot
```

SmolVLA 默认使用 **absolute + MEAN_STD**；`use_delta_joint_actions_aloha` 在
LeRobot 0.7 里仍是 `NotImplementedError`（`configuration_smolvla.py` 第 119–121 行）。M1 只支持 `joint_position_absolute`，其他表示显式拒绝，不做
隐式转换。

## 8. 版本兼容与演进

- Dataset 主版本检查：`check_version_compatibility` 在
  `datasets/utils.py` 第 383–421 行；v2.1 数据集被 v3 代码读取会抛
  `BackwardCompatibilityError`，更新主版本会抛 `ForwardCompatibilityError`。
- 因此 M1 的读取器必须把 `codebase_version == "v3.0"` 作为硬门；
  其他版本返回 `inconclusive`，不做“尽力解析”。
- LeRobot 从 v2.1 到 v3.0 改过存储布局（每 episode 单文件 → 多 episode 合并
  分片）；这说明上游格式仍会演进，JCHENG 的证据层不能直接依赖它。

## 9. 与本项目约束的冲突（设计必须回答）

| 冲突 | 事实 | 设计回答 |
|---|---|---|
| 单 fps vs 异构流 | LeRobot 一个数据集只有一个 `fps`，每帧所有特征必须齐全 | 原生层保留每流时间戳；导出用 `strict` 对齐或显式 `hold`，并记录丢弃/保持帧数 |
| 视频有损 vs 一致性验收 | 默认 MP4（AV1）有损，无法逐像素比对 | M1 默认 `images`（PNG）导出；`videos` 只做 PSNR/帧数验证 |
| 无 provenance 槽位 | `info.json` 丢弃未知字段 | LeRobot 输出根目录加 `jcheng/` sidecar；原生层是溯源事实源 |
| Python 3.12 vs Humble 3.10 | LeRobot 0.7 需要 3.12 | M1 离线在 laptop 3.12；M3 推理位置另设计（laptop / 3.12 容器 / ONNX） |
| 6 GB 显存 vs 默认 batch 64 | 官方示例 batch 64 | M2 先做显存 MVE；不通过则降 batch/冻结/LoRA 或改 ACT 基线 |
| 6 维巧合 | ArmPi 与 SO-100 都是 6 维 | 动作空间 ID 绑定机器人；跨机器人必须显式 map + 重训 |

## 10. 未决验证项（M1 实现前必须实验，不得写成结论）

U1/U2 已在 2026-11-26 的 `/tmp` 探针中解决（见 §10.1），下表只保留未决项。

| ID | 问题 | 验证方式 | 失败后果 |
|---|---|---|---|
| U3 | 6 GB 3060 上 SmolVLA 微调的可用 batch/step 时间 | M2 MVE-0：1 step 前向+反向、峰值显存 | 缩小 batch/冻结/LoRA；仍不行则改 ACT |
| U4 | `empty_cameras=1` 微调 2 相机数据是否稳定 | M2 MVE-1 | 改为三相机数据或改策略输入 |
| U5 | `meta/tasks.parquet` 的 pandas index 列名是否稳定 | 读取多个公开数据集 | 读取器改用 episodes `tasks` 列作为主路径 |
| U6 | 7 维 action 载入 6 维 checkpoint 的行为（报错/忽略） | M2 小实验 | 新建 head，禁止复用 |
| U7 | 视频模式（AV1 编码）写入/读回在本机是否可用 | M2 前用 2-episode 合成集测试 | 视频模式保持 `inconclusive`，M1 只用 images |

### 10.1 U1/U2 实验结果（2026-11-26，/tmp 探针）

| 项 | 结果 | 对设计的影响 |
|---|---|---|
| U1 | PyAV 15.1.0 自带 `libdav1d`，可解码 so101 的 AV1 视频；640×480、11,939 帧、首帧像素可读 | 视频检查与 so101 验收可行；`[video]` extra 版本锁 15.1.0 |
| U2 | `lerobot[dataset]==0.7.0` + `torch==2.15.0+cpu` 可完成图像模式 `create/add_frame/save_episode/finalize`，官方 loader 可读回；state/action 逐值相等 | 官方写入路径可用；M1 核心仍不需要 torch，compat 作业用 CPU 轮子 |
| U2 附带 | 图像模式最终无 `images/`，图像字节在 Parquet；loader 返回 `float32 (C,H,W)` | 一致性检查改为“解码嵌入图像为 uint8 后比较”，不使用 loader 的 float32 视图 |

探针环境：Python 3.12.3；`lerobot==0.7.0`；`torch==2.15.0+cpu`；
`torchvision==0.29.2+cpu`；`torchcodec==0.17.0+cpu`；`av==15.1.0`；
`uv 0.13.8`。这两项是 `/tmp` 探针结果，尚未进入仓库证据；M1 实现阶段要在
`evidence/<date>_m1/` 重新生成可核查记录。

## 11. 一手来源清单

| 来源 | URL/路径 | 用途 |
|---|---|---|
| LeRobot 源码 v0.7.0 | `https://github.com/huggingface/lerobot/tree/v0.7.0`（commit `410c095`） | 全部 API/格式结论 |
| LeRobot PyPI | `https://pypi.org/project/lerobot/0.7.0/` | 版本、Python 要求 |
| Dataset v3 文档 | `https://huggingface.co/docs/lerobot/lerobot-dataset-v3`；仓库 `docs/source/lerobot-dataset-v3.mdx` | 布局、写入流程、finalize |
| 动作表示文档 | 仓库 `docs/source/action_representations.mdx` | absolute/relative/delta |
| SmolVLA 文档 | 仓库 `docs/source/smolvla.mdx` | 微调命令、50 episodes 建议、20k steps |
| Rename map / empty cameras | 仓库 `docs/source/rename_map.mdx` | 相机 key 映射、空相机 |
| SmolVLA 论文 | `https://arxiv.org/abs/2506.01844` | 模型主张、异步推理 |
| SmolVLA 模型卡 | `https://huggingface.co/lerobot/smolvla_base` | 许可、config、用法 |
| 公开数据集 pusht | `https://huggingface.co/datasets/lerobot/pusht` | v3 实测 schema |
| 公开数据集 svla_so101 | `https://huggingface.co/datasets/lerobot/svla_so101_pickplace` | 真机 6 维/2 相机 |
| 公开数据集 svla_so100 | `https://huggingface.co/datasets/lerobot/svla_so100_pickplace` | 对比（470 MB，不选） |
| 本仓库 M0 | `tests/`、`evidence/20261126_scaffold/` | 基线回归 |
