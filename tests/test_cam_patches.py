# SPDX-License-Identifier: LGPL-2.1-or-later
"""cam_patches: each CAM patch applied once, logged once, and a missing API only warns."""

import dataclasses
import sys
import types

import pytest

import FreeCAD
from PathTurnScripts import PathTurnBase, cam_patches


def put(monkeypatch, name, **attrs):
    """A fake module at name (its parents created as needed), undone after the test."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        sub = ".".join(parts[:i])
        if sub not in sys.modules or i == len(parts):
            monkeypatch.setitem(sys.modules, sub, types.ModuleType(sub))
        if i > 1:
            monkeypatch.setattr(sys.modules[".".join(parts[:i - 1])], parts[i - 1], sys.modules[sub], raising=False)
    sys.modules[name].__dict__.update(attrs)
    return sys.modules[name]


class Workbench:
    dressupcmds = ["CAM_DressupDogbone", "CAM_DressupAxisMap", "CAM_DressupPathBoundary"]

    def __init__(self):
        self.menus, self.toolbars, self.offered = [], [], None

    def ContextMenu(self, recipient):
        self.offered = list(self.dressupcmds)

    def Initialize(self):
        self.menus.append("cam")

    def appendToolbar(self, name, commands):
        self.toolbars.append((name, commands))


@dataclasses.dataclass
class ToolContext:
    diameter: float = 6.0
    flutes: int = 4


class TurningProxy(PathTurnBase.ObjectOp):
    pass


@pytest.fixture
def cam(monkeypatch):
    """Fake CAM modules for every patch, and a fresh patch state."""
    monkeypatch.setattr(cam_patches, "_results", {})
    FreeCAD.Console.messages = []
    ns = types.SimpleNamespace()
    ns.workbench_class = type("CAMWorkbench", (Workbench,), {})
    ns.workbench = ns.workbench_class()
    ns.selection = []
    gui = sys.modules["FreeCADGui"]
    monkeypatch.setattr(gui, "getWorkbench", lambda name: ns.workbench, raising=False)
    monkeypatch.setattr(gui, "Selection", types.SimpleNamespace(getSelection=lambda: ns.selection), raising=False)
    put(monkeypatch, "Path.Dressup.Utils", isOp=lambda obj: getattr(obj, "cam", False))

    class CAMSanity:
        def __init__(self, job=None):
            self.job = job

        def get_all_squawks(self, overrides=None):
            return ["cam"], []

        def squawk(self, operator, note, squawkType="NOTE"):
            return {"note": note, "squawkType": squawkType}

    put(monkeypatch, "Path.Main.Sanity.Sanity", CAMSanity=CAMSanity)

    class TaskPanel:
        def cleanup(self, resetEdit):
            return ("cleaned", self.buttonBox)

    put(monkeypatch, "Path.Op.Gui.Base", TaskPanel=TaskPanel)
    put(monkeypatch, "Path.Op.Gui.Selection", select=lambda op: "cam-" + op)
    put(monkeypatch, "PathTurnScripts.PathTurnBaseGui", TURNING_OPS=("TurnFace",), turning_select="turning")
    put(monkeypatch, "Path.Tool.Gui.FeedsSpeedsDialog", adapt_toolbit=lambda tc: ToolContext(),
        find_job_for_tc=lambda tc: "job")
    from PathTurnScripts import TurnFeedsSpeeds
    monkeypatch.setattr(TurnFeedsSpeeds, "stock_diameter", lambda job: 40.0)
    ns.CAMSanity, ns.TaskPanel = CAMSanity, TaskPanel
    return ns


def test_apply_all_applies_and_logs_each_patch_once(cam):
    results = cam_patches.apply_all("Turning", ["CAM_TurnFace"])
    assert results == {fn.__name__: True for fn in cam_patches.PATCHES}
    assert len(results) == 7
    assert len(FreeCAD.Console.of("log")) == 7 and not FreeCAD.Console.of("warning")
    is_op = sys.modules["Path.Dressup.Utils"].isOp
    cam_patches.apply_all("Turning", ["CAM_TurnFace"])
    assert len(FreeCAD.Console.of("log")) == 7
    assert sys.modules["Path.Dressup.Utils"].isOp is is_op


def test_each_patch_is_idempotent_on_its_own(cam):
    cam_patches.apply_all()
    patched = sys.modules["Path.Op.Gui.Selection"].select
    cam_patches.turning_selection_gate()
    cam_patches.accept_turning_ops_as_ops()
    assert sys.modules["Path.Op.Gui.Selection"].select is patched
    assert sys.modules["Path.Dressup.Utils"].isOp("op") is False


def test_a_missing_api_only_warns(cam, monkeypatch):
    monkeypatch.delitem(sys.modules, "Path.Op.Gui.Base")
    monkeypatch.delattr(sys.modules["Path.Op.Gui"], "Base")
    results = cam_patches.apply_all()
    assert results["release_closed_button_boxes"] is False
    assert sum(results.values()) == 6
    warnings = FreeCAD.Console.of("warning")
    assert len(warnings) == 1 and "release_closed_button_boxes" in warnings[0]
    cam_patches.apply_all()
    assert len(FreeCAD.Console.of("warning")) == 1


def test_is_op_accepts_turning_ops(cam):
    cam_patches.apply_all()
    is_op = sys.modules["Path.Dressup.Utils"].isOp
    assert is_op(types.SimpleNamespace(Proxy=TurningProxy()))
    assert is_op(types.SimpleNamespace(cam=True))
    assert not is_op(types.SimpleNamespace(Proxy=object()))


def test_context_menu_offers_turning_dressups_only_for_turning_ops(cam):
    cam_patches.apply_all()
    cam.selection = [types.SimpleNamespace(Proxy=TurningProxy())]
    cam.workbench.ContextMenu("View")
    assert cam.workbench.offered == ["CAM_DressupAxisMap", "CAM_DressupPathBoundary"]
    assert len(cam.workbench.dressupcmds) == 3
    cam.selection = [types.SimpleNamespace(Proxy=object())]
    cam.workbench.ContextMenu("View")
    assert len(cam.workbench.offered) == 3


def test_sanity_adds_the_turning_feed_squawks(cam):
    cam_patches.apply_all()
    feed = types.SimpleNamespace(Value=0.0, UserString="0 mm/min")
    tc = types.SimpleNamespace(Name="TC", Label="TC", VertFeed=feed, HorizFeed=feed,
                               Tool=types.SimpleNamespace(Width=3.0, GroovingDepth=10.0))
    op = types.SimpleNamespace(Proxy=TurningProxy(), ToolController=tc, Label="Groove", Active=True)
    job = types.SimpleNamespace(Operations=types.SimpleNamespace(Group=[op]))
    squawks, critical = cam.CAMSanity(job).get_all_squawks()
    assert squawks[0] == "cam" and len(squawks) == 2
    assert critical[0]["squawkType"] == "WARNING" and "Groove" in critical[0]["note"]


def test_cleanup_drops_the_button_box(cam):
    cam_patches.apply_all()
    panel = cam.TaskPanel()
    panel.buttonBox = "box"
    assert panel.cleanup(True) == ("cleaned", None)


def test_feeds_and_speeds_at_the_stock_diameter_for_inserts(cam):
    cam_patches.apply_all()
    adapt = sys.modules["Path.Tool.Gui.FeedsSpeedsDialog"].adapt_toolbit
    insert = types.SimpleNamespace(Tool=types.SimpleNamespace(ShapeID="isoshape"))
    mill = types.SimpleNamespace(Tool=types.SimpleNamespace(ShapeID="endmill"))
    assert adapt(insert) == ToolContext(diameter=40.0, flutes=1)
    assert adapt(mill) == ToolContext()


def test_initialize_adds_the_turning_toolbar(cam, monkeypatch):
    from PathTurnScripts import TurnAssets
    monkeypatch.setattr(TurnAssets, "refresh_installed_shapes", lambda: [])
    cam_patches.apply_all("Turning", ["CAM_TurnFace"])
    cam.workbench.Initialize()
    assert cam.workbench.menus == ["cam"]
    assert cam.workbench.toolbars == [("Turning", ["CAM_TurnFace"])]


def test_selection_gate_for_turning_ops(cam):
    cam_patches.apply_all()
    select = sys.modules["Path.Op.Gui.Selection"].select
    assert select("TurnFace") == "turning"
    assert select("Pocket") == "cam-Pocket"
