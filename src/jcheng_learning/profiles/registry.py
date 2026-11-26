"""Learning-side robot profiles.

A profile describes the *learning* action/state space, cameras and
capabilities. It references upstream robot descriptions by path and (once
frozen) hash; it never imports ``jcheng-simulation`` or ``jcheng-system``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import DatasetError
from ..io.yaml_io import load_yaml

SCHEMA = "jcheng.learning.robot_adapter.v1"
UNIT_VOCABULARY = {"rad", "rad_s", "m", "m_s", "normalized", "deg", "px", "pulse"}
GRIPPER_SPACES = {"canonical", "raw_joint", "normalized", "linear"}
TRUTH_VALUES = {"measured", "commanded", "unknown"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

PROFILE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Joint:
    name: str
    index: int
    type: str
    unit: str
    lower: float | None = None
    upper: float | None = None
    role: str | None = None


@dataclass(frozen=True)
class Gripper:
    name: str
    index: int
    type: str
    unit: str
    space: str
    closed: float | None = None
    open: float | None = None
    range_known: bool = True
    min: float | None = None
    max: float | None = None
    raw_space: dict[str, Any] | None = None


@dataclass(frozen=True)
class Camera:
    key: str
    role: str
    required: bool
    width: int
    height: int
    rate_hz: float
    frame_id: str | None = None


@dataclass(frozen=True)
class Space:
    id: str
    names: tuple[str, ...]
    units: tuple[str, ...]
    gripper: dict[str, Any] | None = None
    kind: str | None = None
    limits_known: bool = True
    truth_allowed: tuple[str, ...] = ("measured", "commanded")


@dataclass(frozen=True)
class Profile:
    id: str
    version: str
    display_name: str
    dof: int
    has_gripper: bool
    joints: tuple[Joint, ...]
    gripper: Gripper | None
    state_spaces: tuple[Space, ...]
    action_spaces: tuple[Space, ...]
    cameras: tuple[Camera, ...]
    capabilities: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    def state_space(self, space_id: str | None = None) -> Space:
        return _pick_space(self.state_spaces, space_id, "state")

    def action_space(self, space_id: str | None = None) -> Space:
        return _pick_space(self.action_spaces, space_id, "action")


def _pick_space(spaces: tuple[Space, ...], space_id: str | None, kind: str) -> Space:
    if space_id is None:
        if not spaces:
            raise DatasetError(f"profile has no {kind} spaces")
        return spaces[0]
    for space in spaces:
        if space.id == space_id:
            return space
    raise DatasetError(f"unknown {kind} space: {space_id}")


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise DatasetError(f"{where}: missing required field {key!r}")
    return mapping[key]


def _names_units(space: dict[str, Any], where: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    names = tuple(str(name) for name in _require(space, "names", where))
    units = tuple(str(unit) for unit in _require(space, "units", where))
    if not names:
        raise DatasetError(f"{where}: names must not be empty")
    if len(names) != len(units):
        raise DatasetError(f"{where}: names/units length mismatch")
    unknown = sorted(set(units) - UNIT_VOCABULARY)
    if unknown:
        raise DatasetError(f"{where}: unknown units {unknown}")
    return names, units


def _parse_space(raw: dict[str, Any], where: str, *, action: bool) -> Space:
    space_id = str(_require(raw, "id", where))
    names, units = _names_units(raw, where)
    gripper = raw.get("gripper")
    if gripper is not None:
        space = str(gripper.get("space", ""))
        if space not in GRIPPER_SPACES:
            raise DatasetError(f"{where}: invalid gripper space {space!r}")
        gripper = dict(gripper)
    kind = raw.get("kind")
    if action and kind != "joint_position_absolute":
        raise DatasetError(f"{where}: only joint_position_absolute is supported")
    truth_allowed = tuple(str(v) for v in raw.get("truth_allowed", ("measured", "commanded")))
    if not set(truth_allowed) <= TRUTH_VALUES:
        raise DatasetError(f"{where}: invalid truth_allowed {truth_allowed}")
    return Space(
        id=space_id,
        names=names,
        units=units,
        gripper=gripper,
        kind=kind,
        limits_known=bool(raw.get("limits_known", True)),
        truth_allowed=truth_allowed,
    )


def _parse_gripper(raw: dict[str, Any] | None) -> Gripper | None:
    if raw is None:
        return None
    space = str(_require(raw, "space", "gripper"))
    if space not in GRIPPER_SPACES:
        raise DatasetError(f"gripper: invalid space {space!r}")
    unit = str(_require(raw, "unit", "gripper"))
    if unit not in UNIT_VOCABULARY:
        raise DatasetError(f"gripper: invalid unit {unit!r}")
    raw_space = raw.get("raw_space")
    if raw_space is not None and not isinstance(raw_space, dict):
        raise DatasetError("gripper.raw_space must be a mapping")
    return Gripper(
        name=str(_require(raw, "name", "gripper")),
        index=int(_require(raw, "index", "gripper")),
        type=str(_require(raw, "type", "gripper")),
        unit=unit,
        space=space,
        closed=raw.get("closed"),
        open=raw.get("open"),
        range_known=bool(raw.get("range_known", True)),
        min=raw.get("min"),
        max=raw.get("max"),
        raw_space=dict(raw_space) if raw_space else None,
    )


def _parse_profile(data: dict[str, Any], path: Path) -> Profile:
    where = str(path)
    if data.get("schema") != SCHEMA:
        raise DatasetError(f"{where}: schema must be {SCHEMA}")
    profile_id = str(_require(data, "id", where))
    if not _ID_RE.match(profile_id):
        raise DatasetError(f"{where}: invalid id {profile_id!r}")
    version = str(_require(data, "version", where))
    dof = int(_require(data, "dof", where))
    if dof < 1:
        raise DatasetError(f"{where}: dof must be >= 1")

    joints_raw = list(_require(data, "joints", where))
    joints = tuple(
        Joint(
            name=str(_require(item, "name", where)),
            index=int(_require(item, "index", where)),
            type=str(_require(item, "type", where)),
            unit=str(_require(item, "unit", where)),
            lower=item.get("lower"),
            upper=item.get("upper"),
            role=item.get("role"),
        )
        for item in joints_raw
    )
    if len(joints) != dof:
        raise DatasetError(f"{where}: joints length {len(joints)} != dof {dof}")
    if sorted(j.index for j in joints) != list(range(dof)):
        raise DatasetError(f"{where}: joint indices must be 0..{dof - 1}")
    if len({j.name for j in joints}) != len(joints):
        raise DatasetError(f"{where}: duplicate joint names")

    has_gripper = bool(_require(data, "has_gripper", where))
    gripper = _parse_gripper(data.get("gripper"))
    if has_gripper:
        if gripper is None:
            raise DatasetError(f"{where}: has_gripper is true but gripper is missing")
        if gripper.index != dof:
            raise DatasetError(f"{where}: gripper.index must be {dof}")
    elif gripper is not None:
        raise DatasetError(f"{where}: gripper present but has_gripper is false")

    state_spaces = tuple(
        _parse_space(item, f"{where}: state_spaces[{i}]", action=False)
        for i, item in enumerate(_require(data, "state_spaces", where))
    )
    action_spaces = tuple(
        _parse_space(item, f"{where}: action_spaces[{i}]", action=True)
        for i, item in enumerate(_require(data, "action_spaces", where))
    )
    expected_dim = dof + (1 if has_gripper else 0)
    for space in (*state_spaces, *action_spaces):
        if len(space.names) != expected_dim:
            raise DatasetError(
                f"{where}: space {space.id} has {len(space.names)} names, expected {expected_dim}"
            )
    if not state_spaces or not action_spaces:
        raise DatasetError(f"{where}: state_spaces and action_spaces must not be empty")

    cameras = tuple(
        Camera(
            key=str(_require(item, "key", where)),
            role=str(_require(item, "role", where)),
            required=bool(_require(item, "required", where)),
            width=int(_require(item, "width", where)),
            height=int(_require(item, "height", where)),
            rate_hz=float(_require(item, "rate_hz", where)),
            frame_id=item.get("frame_id"),
        )
        for item in data.get("cameras", [])
    )
    if len({c.key for c in cameras}) != len(cameras):
        raise DatasetError(f"{where}: duplicate camera keys")
    for camera in cameras:
        if camera.width <= 0 or camera.height <= 0 or camera.rate_hz <= 0:
            raise DatasetError(f"{where}: camera {camera.key} has invalid dimensions/rate")

    return Profile(
        id=profile_id,
        version=version,
        display_name=str(data.get("display_name", profile_id)),
        dof=dof,
        has_gripper=has_gripper,
        joints=joints,
        gripper=gripper,
        state_spaces=state_spaces,
        action_spaces=action_spaces,
        cameras=cameras,
        capabilities=dict(data.get("capabilities", {})),
        path=path,
    )


def load_profile(profile_id: str) -> Profile:
    if not _ID_RE.match(profile_id):
        raise DatasetError(f"invalid profile id: {profile_id!r}")
    path = PROFILE_DIR / f"{profile_id}.yaml"
    if not path.is_file():
        raise DatasetError(f"unknown profile: {profile_id}")
    return _parse_profile(load_yaml(path), path)


def list_profiles() -> list[str]:
    return sorted(path.stem for path in PROFILE_DIR.glob("*.yaml"))
