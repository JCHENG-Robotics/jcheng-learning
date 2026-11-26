"""RGB8 PNG I/O and integrity helpers.

The native format stores one PNG per camera per frame. LeRobot image-mode
exports embed the same bytes in Parquet, so pixel comparisons must decode
the embedded image rather than assume an ``images/`` tree exists.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from ..errors import DatasetError


def read_rgb(path: Path) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"missing image: {path}")
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"), dtype=np.uint8)
    except (UnidentifiedImageError, OSError) as exc:
        raise DatasetError(f"{path}: cannot decode image: {exc}") from exc


def write_rgb(path: Path, pixels: np.ndarray) -> None:
    array = np.asarray(pixels)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3:
        raise DatasetError(
            f"image must be uint8 HxWx3, got {array.dtype} {array.shape}"
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(path, format="PNG", compress_level=6)


def image_sha256(pixels: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(pixels, dtype=np.uint8).tobytes()).hexdigest()
