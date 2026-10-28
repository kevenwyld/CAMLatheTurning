# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every change the addon makes to CAM's own code, applied once by apply_all(). A patch whose
CAM API is missing logs a warning and costs only its feature."""

import FreeCAD

MARKER = "_turning_patch"

# Dressups that make sense on a lathe path; CAM's others (Dogbone, Drag Knife, Tag,
# Ramp Entry, ...) are for milling paths in the XY plane
TURNING_DRESSUPS = ("CAM_DressupAxisMap", "CAM_DressupPathBoundary", "CAM_DressupPathBoundary2")

PATCHES = []
_results = {}     # patch name -> applied (True) or failed (False), logged once
_toolbar = ("Turning", [])


def patch(fn):
    PATCHES.append(fn)
    return fn


def _mark(fn):
    setattr(fn, MARKER, True)
    return fn


def _patched(fn):
    return getattr(fn, MARKER, False)


def apply_all(toolbar_name="Turning", toolbar_commands=()):
    """Apply each patch once (idempotent) and log the outcome once; returns {name: applied}."""
    global _toolbar
    _toolbar = (toolbar_name, list(toolbar_commands))
    for fn in PATCHES:
        name = fn.__name__
        if name in _results:
            continue
        try:
            fn()
        except Exception as e:
            _results[name] = False
            FreeCAD.Console.PrintWarning("CAM Lathe Turning: CAM patch {} not applied: {}\n".format(name, e))
        else:
            _results[name] = True
            FreeCAD.Console.PrintLog("CAM Lathe Turning: CAM patch {} applied\n".format(name))
    return dict(_results)


def _is_turning_op(obj):
    from PathTurnScripts import PathTurnBase
    return isinstance(getattr(obj, "Proxy", None), PathTurnBase.ObjectOp)


@patch
def accept_turning_ops_as_ops():
    """Path/Dressup/Utils.py isOp(): it tests the proxy's module name, which leaves addon ops
    out of CAM's context menu and dressups. Drop once isOp() checks isinstance(ObjectOp)."""
    import Path.Dressup.Utils as DressupUtils
    cam_is_op = DressupUtils.isOp
    if _patched(cam_is_op):
        return

    def isOp(obj):
        return cam_is_op(obj) or _is_turning_op(obj)

    isOp.__doc__ = cam_is_op.__doc__
    DressupUtils.isOp = _mark(isOp)


@patch
def offer_turning_dressups():
    """InitGui.py CAMWorkbench.ContextMenu: a selection of turning ops is offered only
    TURNING_DRESSUPS (dressupcmds is shortened while the menu is built)."""
    import FreeCADGui
    cls = type(FreeCADGui.getWorkbench("CAMWorkbench"))
    cam_menu = cls.ContextMenu
    if _patched(cam_menu):
        return

    def ContextMenu(self, recipient):
        selection = FreeCADGui.Selection.getSelection()
        turning = bool(selection) and all(_is_turning_op(o) for o in selection)
        saved = getattr(self, "dressupcmds", None)
        if turning and saved is not None:
            self.dressupcmds = [c for c in saved if c in TURNING_DRESSUPS]
        try:
            return cam_menu(self, recipient)
        finally:
            if turning and saved is not None:
                self.dressupcmds = saved

    cls.ContextMenu = _mark(ContextMenu)


def turning_feed_squawks(sanity):
    """CAM Sanity squawks for turning tool controllers with no vertical feed: CAUTION for
    a turning insert, WARNING for a drill or grooving blade (they plunge with it)."""
    from PathTurnScripts import PathTurnBase
    job = getattr(sanity, "job", None)
    if job is None or not hasattr(job, "Operations"):
        return []
    users = {}
    for op in job.Operations.Group:
        proxy = getattr(op, "Proxy", None)
        tc = getattr(op, "ToolController", None)
        if not isinstance(proxy, PathTurnBase.ObjectOp) or tc is None or not getattr(op, "Active", True):
            continue
        if getattr(proxy, "uses_threading_tool", False):
            continue
        users.setdefault(tc.Name, (tc, []))[1].append(op.Label)
    squawks = []
    for tc, labels in users.values():
        if tc.VertFeed.Value > 0:
            continue
        tool = getattr(tc, "Tool", None)
        plunging = tool is not None and (PathTurnBase.is_drill_tool(tool) or PathTurnBase.is_grooving_tool(tool))
        where = "Tool Controller '{}' ({})".format(tc.Label, ", ".join(labels))
        if plunging:
            note = ("{}: No vertical feedrate; a drill or a grooving or parting blade plunges with it. Set one. "
                    "Falling back to the horizontal feedrate of {}").format(where, tc.HorizFeed.UserString)
            kind = "WARNING"
        else:
            note = "{}: No vertical feedrate, falling back to the horizontal feedrate of {}".format(where, tc.HorizFeed.UserString)
            kind = "CAUTION"
        squawks.append(sanity.squawk("CAMSanity", note, squawkType=kind))
    return squawks


@patch
def add_turning_feed_checks():
    """Path/Main/Sanity/Sanity.py CAMSanity.get_all_squawks: the post dialog's warnings and
    the Sanity report get turning_feed_squawks()."""
    import Path.Main.Sanity.Sanity as Sanity
    cls = Sanity.CAMSanity
    original = cls.get_all_squawks
    if _patched(original):
        return

    def get_all_squawks(self, *args, **kwargs):
        all_squawks, critical = original(self, *args, **kwargs)
        try:
            extra = turning_feed_squawks(self)
        except Exception as e:
            FreeCAD.Console.PrintLog("Turning feed checks failed: {}\n".format(e))
            extra = []
        return (list(all_squawks) + extra,
                list(critical) + [s for s in extra if s["squawkType"] in ("WARNING", "CAUTION")])

    cls.get_all_squawks = _mark(get_all_squawks)


@patch
def release_closed_button_boxes():
    """Path/Op/Gui/Base.py TaskPanel.cleanup: drop the reference to the dialog's button box
    before Qt deletes the widgets (a stale PySide wrapper otherwise)."""
    import Path.Op.Gui.Base as PathOpGui
    panel = PathOpGui.TaskPanel
    cleanup = panel.cleanup
    if _patched(cleanup):
        return

    def release(self, resetEdit):
        self.buttonBox = None
        for page in list(getattr(self, "featurePages", []) or []):
            point = getattr(page, "getPoint", None)
            if point is not None and hasattr(point, "buttonBox"):
                point.buttonBox = None
        return cleanup(self, resetEdit)

    panel.cleanup = _mark(release)


@patch
def feeds_speeds_for_inserts():
    """Path/Tool/Gui/FeedsSpeedsDialog.py adapt_toolbit: a turning tool's rpm is worked out
    at the stock's diameter with one cutting edge, not at the insert's size."""
    import dataclasses
    import Path.Tool.Gui.FeedsSpeedsDialog as dialog
    from PathTurnScripts import TurnFeedsSpeeds
    cam_adapt = dialog.adapt_toolbit
    if _patched(cam_adapt):
        return

    def adapt_toolbit(tc):
        ctx = cam_adapt(tc)
        tool = getattr(tc, "Tool", None)
        if tool is None or not TurnFeedsSpeeds.is_turning_tool(tool):
            return ctx
        diameter = TurnFeedsSpeeds.stock_diameter(dialog.find_job_for_tc(tc))
        return dataclasses.replace(ctx, diameter=diameter if diameter > 0 else ctx.diameter, flutes=1)

    dialog.adapt_toolbit = _mark(adapt_toolbit)


@patch
def add_turning_toolbar():
    """InitGui.py CAMWorkbench.Initialize: a Turning toolbar (so it belongs to the CAM
    workbench), and the addon's tool shapes refreshed in CAM's store."""
    import FreeCADGui
    cls = type(FreeCADGui.getWorkbench("CAMWorkbench"))
    cam_initialize = cls.Initialize
    if _patched(cam_initialize):
        return

    def Initialize(self):
        cam_initialize(self)
        try:
            from PathTurnScripts import TurnAssets
            TurnAssets.refresh_installed_shapes()
        except Exception as e:
            FreeCAD.Console.PrintLog("TurningAddon: refreshing the tool shapes failed: {}\n".format(e))
        try:
            self.appendToolbar(*_toolbar)
        except Exception as e:
            FreeCAD.Console.PrintWarning("Turning: could not add the Turning toolbar: {}\n".format(e))

    cls.Initialize = _mark(Initialize)


@patch
def turning_selection_gate():
    """Path/Op/Gui/Selection.py select(): it sends the turning ops to TURNGate (holes only)
    or fails on unknown names; they get PathTurnBaseGui's gate instead."""
    import Path.Op.Gui.Selection as PathSelection
    from PathTurnScripts import PathTurnBaseGui
    cam_select = PathSelection.select
    if _patched(cam_select):
        return

    def select(op):
        if op in PathTurnBaseGui.TURNING_OPS:
            return PathTurnBaseGui.turning_select
        return cam_select(op)

    PathSelection.select = _mark(select)
