# M1 evidence — offline dataset gate (2026-11-26)

Status: **M1 implementation evidence, L1 (unit/integration, no robot)**.
This directory records the commands and summaries only. Datasets, images,
Parquet/MP4 outputs and model weights stay outside the repository.

## 1. Scope

- Native dataset schema and reader/writer (`jcheng.dataset.v1`).
- Robot profiles: ArmPi Ultra, Gate-2, Piper X, SO-101 (import only),
  PushT 2D and a probe fixture.
- Validator (`DQ-*`), quality report and CLI.
- LeRobot Dataset v3.0 reader and importer (no torch in the core path).
- LeRobot v3.0 exporter through the official writer (optional extra).
- Deterministic synthetic generator.
- No training, no policy, no device, no DDS, no motion.

## 2. Environment

| Item | Value |
|---|---|
| Host | Linux x86_64, RTX 3060 Laptop 6 GB (unused here) |
| Core Python | 3.12.3 |
| Core lock | `uv.lock`, SHA-256 `sha256:a866bfd19d1750faba90b51dd0d7b93e2ce720d1f78b66617a9deec54ba013e7` |
| Core install | `uv run --frozen --extra test` |
| Compat env | `lerobot 0.7.0`, `torch 2.15.0+cpu`, `torchvision 0.29.2+cpu`, `torchcodec 0.17.0+cpu`, `av 15.1.0`, `pyarrow 26.0.1`, `numpy 2.2.6`, `Pillow 13.0.0`, `datasets 5.2.0` |
| Robot access | none |

Details: [compat-env.txt](compat-env.txt).

## 3. Gates

| Gate | Result | Evidence |
|---|---|---|
| Repository gate | pass | [gate.txt](gate.txt) |
| Unit/integration tests | 65 passed | [pytest.txt](pytest.txt) |
| No-hardware static tests | 4 passed | [no-hardware.txt](no-hardware.txt) |
| M0 regression | 13 original tests still pass | [pytest.txt](pytest.txt) |

## 4. Datasets and conversion results

| Item | Result | Evidence |
|---|---|---|
| Deterministic synthetic ArmPi set | 2 episodes / 8 frames; `result: pass`; `root_sha256: sha256:6c176d24b23733edb379f42060d2061308a1b60bb01dfb5d19f35921aa3fc04c` | [synth.txt](synth.txt), [synthetic-quality.json](synthetic-quality.json) |
| Synthetic native → LeRobot images → official loader | 2 episodes / 8 frames; state diff 0; action diff 0; image pixel diff 0 | [synthetic-roundtrip.json](synthetic-roundtrip.json) |
| `lerobot/pusht` import (206 eps / 25,650 frames) | `result: pass`; state diff 0; action diff 0 | [pusht-import.txt](pusht-import.txt), [pusht-quality.json](pusht-quality.json), [pusht-diff.json](pusht-diff.json) |
| `lerobot/svla_so101_pickplace` import (50 eps / 11,939 frames) | `result: inconclusive` (gripper range unknown in the public data); no error | [so101-import.txt](so101-import.txt), [so101-quality.json](so101-quality.json) |
| SO-101 native → LeRobot (tabular) → official loader | 50 episodes / 11,939 frames; state diff 0; action diff 0 | [so101-roundtrip.json](so101-roundtrip.json) |
| 17-case anomaly matrix | all expected `DQ-*` checks fail; CLI exits 1 | [anomaly-matrix.json](anomaly-matrix.json) |

Pinned public revisions:

- `lerobot/pusht` — `7628202a2180972f291ba1bc6723834921e72c19` (MIT,
  7.7 MB downloaded for tabular metadata).
- `lerobot/svla_so101_pickplace` — `f641879e22172be7e8161d5e6c1503c2d2feb657`
  (Apache-2.0, 0.4 MB metadata/tabular downloaded; one 39 MB AV1 video was
  decoded separately by U1 but is not part of this evidence).

## 5. Reproduce

```bash
# Core gate (locked environment, no torch)
uv run --frozen --extra test python -m pytest -q
bash scripts/check_repo_gate.sh

# Deterministic synthetic set
uv run --frozen --extra test python -m jcheng_learning.cli synth \
  --profile armpi_ultra --out /tmp/m1-synth --episodes 2 --frames 8 \
  --fps 10 --seed 20261126 --created-at 2026-11-26T00:00:00+08:00 \
  --image-size 64x48
uv run --frozen --extra test python -m jcheng_learning.cli validate \
  /tmp/m1-synth/synthetic-armpi_ultra-01352906 --report /tmp/m1-report.json

# Compat job (operator laptop, CPU or CUDA torch)
uv sync --frozen --extra lerobot
uv run --frozen --extra lerobot python -c "import lerobot; print(lerobot.__version__)"
```

The compat results above were produced with a `/tmp` venv containing
`lerobot[dataset]==0.7.0` and `torch==2.15.0+cpu`; the exact versions are in
[compat-env.txt](compat-env.txt).

## 6. Limitations

- The compat loader ran on CPU. No GPU, CUDA, training or inference was
  exercised.
- SO-101 import is tabular only (`--no-images`): the 39 MB AV1 video was decoded
  by U1, but a full 11,939-frame image import was not run.
- The SO-101 quality report is `inconclusive`, not pass: the public dataset does
  not provide a gripper range. This is intentional; an unknown bound is never a
  pass.
- Image-mode LeRobot datasets embed image bytes in Parquet and have no final
  `images/` directory; the pixel comparison decodes the embedded image.
- No robot, camera, serial, CAN, GPIO or DDS access. Nothing here is L4 replay
  or L5 hardware validation.

## 6.1 Implementation deviations

- Code-level validators cover the data contract; only the quality report has a
  standalone JSON Schema.
- `strict` sampling only; `hold` is rejected.
- `import` is LeRobot v3 only; historical native data is validated directly.
- `videos` export is unverified (U7); the evidence uses `images`.
- `pusht_2d` and `probe_2d` are benchmark/test profiles, not JCHENG robots.

## 7. File checksums

[SHA256SUMS](SHA256SUMS) covers every file in this directory except itself.

## 8. Related design documents

- [00-INDEX.md](../../docs/m1/00-INDEX.md)
- [03-DESIGN.md](../../docs/m1/03-DESIGN.md)
- [04-DATA-CONTRACT.md](../../docs/m1/04-DATA-CONTRACT.md)
