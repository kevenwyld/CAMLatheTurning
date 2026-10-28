# SPDX-License-Identifier: LGPL-2.1-or-later
"""PathTurnBase.show_values: worked-out values written only when they change, without
leaving an untouched object touched."""

import FreeCAD
from PathTurnScripts.PathTurnBase import show_values


class Obj:
    """A document object: setting a property touches it."""

    def __init__(self, touched=False, **props):
        object.__setattr__(self, "State", ["Touched"] if touched else [])
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "purged", 0)
        for name, value in props.items():
            object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        self.writes.append(name)
        if "Touched" not in self.State:
            self.State.append("Touched")
        object.__setattr__(self, name, value)

    def purgeTouched(self):
        object.__setattr__(self, "purged", self.purged + 1)
        self.State.remove("Touched")


def length(mm):
    return FreeCAD.Units.Quantity(mm, FreeCAD.Units.Length)


def test_only_changed_values_are_written():
    obj = Obj(MaxDiameter=length(20.0), LeadIn=length(1.0), Passes=6, SurfaceSpeed=200.0,
              SurfaceSpeedSource="tool preset", LastRefusal=[])
    wrote = show_values(obj, {"MaxDiameter": 20.0 + 1e-10, "LeadIn": 1.5, "Passes": 6, "SurfaceSpeed": 200.0,
                              "SurfaceSpeedSource": "tool preset", "LastRefusal": [], "Missing": 1.0})
    assert wrote and obj.writes == ["LeadIn"]
    assert obj.LeadIn.Value == 1.5 and isinstance(obj.LeadIn, FreeCAD.Units.Quantity)


def test_each_kind_of_value_is_compared_as_its_property():
    obj = Obj(Passes=6, SurfaceSpeed=200.0, SurfaceSpeedSource="a", LastRefusal=["check", "why"])
    show_values(obj, {"Passes": 7, "SurfaceSpeed": 180.0, "SurfaceSpeedSource": "b", "LastRefusal": []})
    assert obj.writes == ["Passes", "SurfaceSpeed", "SurfaceSpeedSource", "LastRefusal"]
    assert (obj.Passes, obj.SurfaceSpeed, obj.SurfaceSpeedSource, obj.LastRefusal) == (7, 180.0, "b", [])


def test_tolerance():
    obj = Obj(RunOut=length(1.0))
    assert not show_values(obj, {"RunOut": 1.0 + 5e-8}, tol=1e-7)
    assert show_values(obj, {"RunOut": 1.0 + 5e-8})


def test_an_untouched_object_is_left_untouched():
    obj = Obj(MaxDiameter=length(20.0))
    show_values(obj, {"MaxDiameter": 25.0})
    assert obj.purged == 1 and obj.State == []


def test_a_touched_object_stays_touched():
    obj = Obj(touched=True, MaxDiameter=length(20.0))
    show_values(obj, {"MaxDiameter": 25.0})
    assert obj.purged == 0 and obj.State == ["Touched"]


def test_nothing_written_nothing_purged():
    obj = Obj(MaxDiameter=length(20.0))
    assert not show_values(obj, {"MaxDiameter": 20.0})
    assert obj.purged == 0 and not obj.writes
