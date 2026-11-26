"""Explicit action-space mapping.

A mapping is a per-dimension affine rule set. The executor never reorders by
index without a rule, never matches names fuzzily and never converts units
implicitly: ``unit_in`` and ``unit_out`` must match in M1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from .errors import DatasetError
from .io.yaml_io import load_yaml

SCHEMA = "jcheng.action-map.v1"
_UNITS = {"rad", "rad_s", "m", "m_s", "normalized", "deg", "px", "pulse"}
_TRANSFER = {"none", "research-only", "validated"}


@dataclass(frozen=True)
class Rule:
    to_index: int
    to_name: str
    from_index: int
    from_name: str
    scale: float
    offset: float
    unit_in: str
    unit_out: str
    note: str | None = None


@dataclass(frozen=True)
class ActionMap:
    from_space: str
    to_space: str
    transfer_claim: str
    rules: tuple[Rule, ...]
    unmapped: tuple[str, ...]

    @property
    def target_size(self) -> int:
        return len(self.rules)

    def apply(self, values: list[float] | tuple[float, ...]) -> list[float]:
        source = [float(value) for value in values]
        result = [0.0] * self.target_size
        for rule in self.rules:
            if rule.from_index >= len(source):
                raise DatasetError(
                    f"action map: source has {len(source)} values, rule needs index "
                    f"{rule.from_index}"
                )
            value = source[rule.from_index] * rule.scale + rule.offset
            if not math.isfinite(value):
                raise DatasetError("action map produced a non-finite value")
            result[rule.to_index] = value
        return result


def load_action_map(path: Path) -> ActionMap:
    data = load_yaml(path)
    if data.get("schema") != SCHEMA:
        raise DatasetError(f"{path}: schema must be {SCHEMA}")
    from_space = str(data.get("from_space", ""))
    to_space = str(data.get("to_space", ""))
    if not from_space or not to_space:
        raise DatasetError(f"{path}: from_space/to_space are required")
    transfer = str(data.get("transfer_claim", "none"))
    if transfer not in _TRANSFER:
        raise DatasetError(f"{path}: invalid transfer_claim {transfer!r}")
    rules_raw = data.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise DatasetError(f"{path}: rules must not be empty")
    rules: list[Rule] = []
    for index, item in enumerate(rules_raw):
        if not isinstance(item, dict):
            raise DatasetError(f"{path}: rule {index} is not a mapping")
        unit_in = str(item.get("unit_in", ""))
        unit_out = str(item.get("unit_out", ""))
        if unit_in not in _UNITS or unit_out not in _UNITS:
            raise DatasetError(f"{path}: rule {index} has an invalid unit")
        if unit_in != unit_out:
            raise DatasetError(
                f"{path}: rule {index} changes units ({unit_in}->{unit_out}); "
                "unit conversion is not implicit in M1"
            )
        rule = Rule(
            to_index=int(item["to_index"]),
            to_name=str(item["to_name"]),
            from_index=int(item["from_index"]),
            from_name=str(item["from_name"]),
            scale=float(item.get("scale", 1.0)),
            offset=float(item.get("offset", 0.0)),
            unit_in=unit_in,
            unit_out=unit_out,
            note=item.get("note"),
        )
        if not all(math.isfinite(v) for v in (rule.scale, rule.offset)):
            raise DatasetError(f"{path}: rule {index} has a non-finite scale/offset")
        rules.append(rule)
    rules.sort(key=lambda rule: rule.to_index)
    expected = list(range(len(rules)))
    if [rule.to_index for rule in rules] != expected:
        raise DatasetError(f"{path}: to_index must cover 0..{len(rules) - 1} exactly once")
    if len({rule.to_name for rule in rules}) != len(rules):
        raise DatasetError(f"{path}: duplicate to_name")
    unmapped = data.get("unmapped", [])
    if not isinstance(unmapped, list):
        raise DatasetError(f"{path}: unmapped must be a list")
    return ActionMap(
        from_space=from_space,
        to_space=to_space,
        transfer_claim=transfer,
        rules=tuple(rules),
        unmapped=tuple(str(item) for item in unmapped),
    )
