# SPDX-License-Identifier: LGPL-2.1-or-later
"""PathTurnBase.lathe_tool: the tool bit's values reach liblathe unchanged."""

import pytest

from PathTurnScripts.PathTurnBase import TOOL_SETTERS, lathe_tool


class Tool:
    """liblathe's Tool validators (tip angle (0, 180], rotation [0, 360), nose radius >= 0)."""

    def set_tip_angle(self, angle):
        if not 0 < angle <= 180:
            raise ValueError("Tip angle must be more than 0 and at most 180 degrees, got %r" % angle)
        self.tip_angle = angle

    def set_edge_length(self, length):
        if not length > 0:
            raise ValueError("Edge length must be above zero, got %r" % length)
        self.edge_length = length

    def set_nose_radius(self, radius):
        if not radius >= 0:
            raise ValueError("Nose radius must be zero or more, got %r" % radius)
        self.nose_radius = radius

    def set_rotation(self, rotation):
        if not 0 <= rotation < 360:
            raise ValueError("Rotation must be at least 0 and less than 360 degrees, got %r" % rotation)
        self.tool_rotation = rotation


def values(**changes):
    v = {"TipAngle": 80.0, "EdgeLength": 12.0, "TipRadius": 0.4, "Rotation": 15.0}
    v.update(changes)
    return v


@pytest.mark.parametrize("changes", [{}, {"TipAngle": 90.0, "Rotation": 0.0}, {"TipAngle": 180.0},
                                     {"TipRadius": 0.0}, {"Rotation": 359.0}])
def test_values_pass_through_unchanged(changes):
    tool = lathe_tool(Tool(), "CCMT", values(**changes))
    v = values(**changes)
    assert (tool.tip_angle, tool.edge_length, tool.nose_radius, tool.tool_rotation) == (
        v["TipAngle"], v["EdgeLength"], v["TipRadius"], v["Rotation"])


@pytest.mark.parametrize("prop, value", [("TipAngle", 0.0), ("TipAngle", 181.0), ("EdgeLength", 0.0),
                                         ("TipRadius", -0.1), ("Rotation", 360.0), ("Rotation", -5.0)])
def test_a_refused_value_names_the_tool_and_parameter(prop, value):
    with pytest.raises(RuntimeError) as raised:
        lathe_tool(Tool(), "My insert", values(**{prop: value}))
    message = str(raised.value)
    assert "My insert" in message and prop in message and repr(value) in message
    assert isinstance(raised.value.__cause__, ValueError)


def test_every_insert_parameter_is_set():
    assert [p for p, _ in TOOL_SETTERS] == ["TipAngle", "EdgeLength", "TipRadius", "Rotation"]
