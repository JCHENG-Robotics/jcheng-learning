from pathlib import Path

import pytest

from jcheng_learning.action_map import load_action_map
from jcheng_learning.errors import DatasetError

MAP = Path(__file__).resolve().parents[1] / "src/jcheng_learning/action_maps/armpi_ultra_raw_to_canonical.yaml"


def test_armpi_raw_to_canonical():
    mapping = load_action_map(MAP)
    assert mapping.target_size == 6
    assert mapping.transfer_claim == "none"
    closed = mapping.apply([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    opened = mapping.apply([0.0, 0.0, 0.0, 0.0, 0.0, -2.22])
    assert closed[-1] == 0.0
    assert opened[-1] == pytest.approx(2.22)


def test_short_source_is_rejected():
    mapping = load_action_map(MAP)
    with pytest.raises(DatasetError, match="source has 5"):
        mapping.apply([0.0] * 5)


def test_unit_change_is_rejected(tmp_path):
    text = MAP.read_text().replace("unit_in: rad, unit_out: rad", "unit_in: deg, unit_out: rad", 1)
    path = tmp_path / "map.yaml"
    path.write_text(text)
    with pytest.raises(DatasetError, match="changes units"):
        load_action_map(path)


def test_duplicate_target_is_rejected(tmp_path):
    text = MAP.read_text().replace("to_index: 1,", "to_index: 0,", 1)
    path = tmp_path / "map.yaml"
    path.write_text(text)
    with pytest.raises(DatasetError, match="to_index"):
        load_action_map(path)
