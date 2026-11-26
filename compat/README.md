# LeRobot compatibility suite (operator-run)

This directory is **not** part of the core package or CI. It is the repeatable
operator check for the optional LeRobot path, using the official
`LeRobotDataset` writer/loader as the oracle.

```bash
# Create/refresh the compat environment (torch is pulled by lerobot)
uv sync --frozen --extra lerobot --extra video

# Synthetic image-mode round-trip
uv run --extra lerobot python compat/run_compat.py --profile armpi_ultra \
  --workdir /tmp/jcheng-compat

# A native dataset (tabular or image) can be exported and loaded too
uv run --extra lerobot python compat/run_compat.py \
  --native /path/to/dataset --workdir /tmp/jcheng-compat --no-images
```

The script prints a JSON result and exits non-zero on any mismatch. It never
touches a robot, camera, DDS domain or network (the optional public-dataset
import is performed separately by `jcheng-dataset import`).
