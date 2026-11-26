from jcheng_learning.profiles import list_profiles, load_profile


def test_profile_set():
    assert list_profiles() == ["armpi_ultra", "gate2_arm", "piper_x", "probe_2d", "pusht_2d", "so101_follower"]


def test_armpi_profile():
    profile = load_profile("armpi_ultra")
    assert profile.dof == 5
    assert profile.has_gripper
    assert len(profile.joints) == 5
    space = profile.action_space()
    assert space.id == "armpi_ultra.joint_position_absolute.v1"
    assert space.names == ("joint1", "joint2", "joint3", "joint4", "joint5", "r_joint")
    assert space.units == ("rad",) * 6
    assert profile.gripper is not None
    assert profile.gripper.space == "canonical"
    assert profile.gripper.closed == 0.0
    assert profile.gripper.open == 2.22
    assert [camera.key for camera in profile.cameras] == ["external", "wrist"]


def test_gate2_profile_has_no_gripper():
    profile = load_profile("gate2_arm")
    assert profile.dof == 2
    assert not profile.has_gripper
    assert profile.gripper is None
    assert profile.action_space().names == ("joint1", "joint2")


def test_piper_profile_is_seven_dimensional():
    profile = load_profile("piper_x")
    assert profile.dof == 6
    assert profile.has_gripper
    space = profile.action_space()
    assert len(space.names) == 7
    assert space.names[-1] == "gripper"
    assert space.units[-1] == "m"
    assert profile.gripper is not None
    assert profile.gripper.space == "linear"


def test_so101_profile_is_import_only_and_non_si():
    profile = load_profile("so101_follower")
    assert profile.dof == 5
    space = profile.action_space()
    assert len(space.names) == 6
    assert space.names[0] == "shoulder_pan.pos"
    assert space.units[:5] == ("deg",) * 5
    assert space.units[-1] == "normalized"
    assert not space.limits_known
    assert profile.gripper is not None
    assert profile.gripper.range_known is False
