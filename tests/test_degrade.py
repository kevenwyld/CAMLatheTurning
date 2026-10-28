# SPDX-License-Identifier: LGPL-2.1-or-later
"""The addon loads without optional CAM APIs and without liblathe's submodule, and says why."""

import importlib
import os
import sys
import types

import pytest

import FreeCAD
from PathTurnScripts import PathTurnAddonHelpers, PathTurnBase, TurnFeedsSpeeds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def feeds_speeds(monkeypatch):
    """Fake Path.Tool.FeedsSpeeds; TurnFeedsSpeeds reloaded with it, and without it afterwards."""
    def install(score=True):
        names = dict(MaterialContext=object, OpContext=object, ToolContext=object,
                     derive_preset_label=lambda p, d: d, get_presets=lambda tool: [])
        fs = types.ModuleType("Path.Tool.FeedsSpeeds")
        fs.__dict__.update(names)
        providers = types.ModuleType("Path.Tool.FeedsSpeeds.providers")
        providers.MachinabilityProvider = providers.ToolPresetProvider = object
        if score:
            providers._score_preset = lambda *a: 1.0
        fs.providers = providers
        monkeypatch.setitem(sys.modules, "Path.Tool.FeedsSpeeds", fs)
        monkeypatch.setitem(sys.modules, "Path.Tool.FeedsSpeeds.providers", providers)
        monkeypatch.setattr(sys.modules["Path.Tool"], "FeedsSpeeds", fs, raising=False)
        return importlib.reload(TurnFeedsSpeeds)
    yield install
    monkeypatch.undo()
    importlib.reload(TurnFeedsSpeeds)


def test_without_feeds_and_speeds_css_is_unavailable():
    assert TurnFeedsSpeeds.available is False
    assert TurnFeedsSpeeds.check_css(False) is False
    with pytest.raises(RuntimeError, match="Feeds & Speeds"):
        TurnFeedsSpeeds.check_css(True)


def test_with_feeds_and_speeds_css_is_available(feeds_speeds):
    module = feeds_speeds()
    assert module.available and module.check_css(True) and module._score_preset is not None


def test_without_the_private_scorer_only_the_preset_label_is_lost(feeds_speeds):
    module = feeds_speeds(score=False)
    assert module.available and module._score_preset is None


class CssOp(PathTurnBase.ObjectOp):
    css_op_type = "profile"


def test_apply_css_raises_only_when_css_is_switched_on():
    op = CssOp()
    off = types.SimpleNamespace(ConstantSurfaceSpeed=False)
    assert op.apply_css(off) is None
    with pytest.raises(RuntimeError, match="Constant surface speed"):
        op.apply_css(types.SimpleNamespace(ConstantSurfaceSpeed=True))


def test_liblathe_path_is_put_first_once(tmp_path):
    lib = str(tmp_path / "LibLathe")
    assert PathTurnAddonHelpers.needs_path(lib, ["/usr/lib/python3"], None)
    assert not PathTurnAddonHelpers.needs_path(lib, ["/usr/lib/python3", lib], None)
    assert not PathTurnAddonHelpers.needs_path(lib + os.sep, [lib], None)
    origin = os.path.join(lib, "liblathe", "__init__.py")
    assert not PathTurnAddonHelpers.needs_path(lib, [], origin)
    assert PathTurnAddonHelpers.needs_path(lib, [], "/site-packages/liblathe/__init__.py")


def test_the_vendored_liblathe_is_on_the_path_at_most_once():
    lib = os.path.join(ROOT, "LibLathe")
    assert sys.path.count(lib) <= 1


def run_init_gui(monkeypatch, tmp_path, with_liblathe):
    addon = tmp_path / "addon"
    (addon / "PathTurnScripts").mkdir(parents=True)
    if with_liblathe:
        (addon / "LibLathe" / "liblathe").mkdir(parents=True)
        (addon / "LibLathe" / "liblathe" / "__init__.py").write_text("")
    package = types.ModuleType("PathTurnScripts")
    package.__file__ = str(addon / "PathTurnScripts" / "__init__.py")
    monkeypatch.setitem(sys.modules, "PathTurnScripts", package)
    monkeypatch.setitem(sys.modules, "InitTurningAddon", None)    # importing it raises ImportError
    FreeCAD.Console.messages = []
    with open(os.path.join(ROOT, "InitGui.py")) as f:
        exec(compile(f.read(), "InitGui.py", "exec"), {})


def test_init_gui_names_the_submodule_command_when_liblathe_is_missing(monkeypatch, tmp_path):
    run_init_gui(monkeypatch, tmp_path, with_liblathe=False)
    errors = FreeCAD.Console.of("error")
    assert len(errors) == 1 and "git submodule update --init" in errors[0]


def test_init_gui_loads_the_addon_when_liblathe_is_there(monkeypatch, tmp_path):
    with pytest.raises(ImportError):
        run_init_gui(monkeypatch, tmp_path, with_liblathe=True)
    assert not FreeCAD.Console.of("error")
