# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2020 Daniel Wood <s.d.wood.82@googlemail.com>            *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import os

import FreeCAD
import FreeCADGui

# register the ISO turning-insert toolbit shape
from PathTurnScripts import TurnToolShapes  # noqa: F401

# import all turning operations
from PathTurnScripts import PathTurnFaceGui  # noqa: F401
from PathTurnScripts import PathTurnChamferGui  # noqa: F401
from PathTurnScripts import PathTurnDrillGui  # noqa: F401
from PathTurnScripts import PathTurnGrooveGui  # noqa: F401
from PathTurnScripts import PathTurnGrooveTurnGui  # noqa: F401
from PathTurnScripts import PathTurnThreadGui  # noqa: F401
from PathTurnScripts import PathTurnPartoffGui  # noqa: F401
from PathTurnScripts import PathTurnProfileGui  # noqa: F401
from PathTurnScripts import PathTurnRoughGui  # noqa: F401
from PathTurnScripts import PathTurnToolHelperGui  # noqa: F401
from PathTurnScripts import TurnAssets  # noqa: F401
from PathTurnScripts import TurnSpindleAxis  # noqa: F401

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join(__dir__, 'Gui/Resources/Icons')

# The commands' pixmaps are named after the icon files (e.g. 'CAM-TurnFace'),
# so adding the folder to the icon search path lets FreeCAD resolve them.
FreeCADGui.addIconPath(iconPath)

# Turning commands, in menu order
COMMANDS = ['CAM_TurnFace', 'CAM_TurnDrill', 'CAM_TurnRough', 'CAM_TurnProfile', 'CAM_TurnChamfer', 'CAM_TurnGroove', 'CAM_TurnGrooveTurn', 'CAM_TurnThread', 'CAM_TurnPartoff',
            'CAM_TurnSpindleAxis', 'CAM_TurnToolHelper',
            'CAM_TurnInstallTools']

# Existing CAM command to insert after. It only exists in the CAM workbench's
# menu, so the manipulator is a no-op in every other workbench.
ANCHOR = 'CAM_Pocket3D'
TOOLBAR = 'Turning'


class TurningMenuManipulator:
    """Adds the turning commands to the CAM menu. FreeCAD rebuilds menus on every
    workbench switch; a manipulator is re-applied each time, so the entries persist."""

    def modifyMenuBar(self):
        # Result: ... CAM_Pocket3D, Separator, <turning commands>, Separator ...
        items = []
        previous = ANCHOR
        for cmd in COMMANDS:
            # chain each insert after the previous one to keep the order
            items.append({"insert": cmd, "menuItem": previous, "after": ""})
            previous = cmd
        # finally put a separator between the anchor and the first turning command
        items.append({"insert": "Separator", "menuItem": ANCHOR, "after": ""})
        return items


FreeCADGui.addWorkbenchManipulator(TurningMenuManipulator())


def accept_turning_ops_as_ops():
    """Patch Path.Dressup.Utils.isOp() to accept the turning operations: it tests the
    proxy's module name, which leaves addon ops out of CAM's context menu and dressups.
    TODO: drop once upstream isOp() checks isinstance(obj.Proxy, Path.Op.Base.ObjectOp)."""
    try:
        import Path.Dressup.Utils as DressupUtils
        from PathTurnScripts import PathTurnBase
    except Exception:
        return
    cam_is_op = DressupUtils.isOp
    if getattr(cam_is_op, "accepts_turning_ops", False):
        return

    def isOp(obj):
        if cam_is_op(obj):
            return True
        return isinstance(getattr(obj, "Proxy", None), PathTurnBase.ObjectOp)

    isOp.__doc__ = cam_is_op.__doc__
    isOp.accepts_turning_ops = True
    DressupUtils.isOp = isOp


accept_turning_ops_as_ops()


# Dressups that make sense on a lathe path; CAM's others (Dogbone, Drag
# Knife, Tag, Ramp Entry, ...) are for milling paths in the XY plane
TURNING_DRESSUPS = ("CAM_DressupAxisMap", "CAM_DressupPathBoundary", "CAM_DressupPathBoundary2")


def offer_turning_dressups():
    """Patch CAMWorkbench.ContextMenu so a selection of turning operations is offered
    only TURNING_DRESSUPS (its dressupcmds list is shortened while the menu is built)."""
    try:
        workbench = FreeCADGui.getWorkbench("CAMWorkbench")
        from PathTurnScripts import PathTurnBase
    except Exception:
        return
    cam_menu = getattr(type(workbench), "ContextMenu", None)
    if cam_menu is None or getattr(cam_menu, "offers_turning_dressups", False):
        return

    def ContextMenu(self, recipient):
        selection = FreeCADGui.Selection.getSelection()
        turning = bool(selection) and all(
            isinstance(getattr(o, "Proxy", None), PathTurnBase.ObjectOp) for o in selection)
        saved = getattr(self, "dressupcmds", None)
        if turning and saved is not None:
            self.dressupcmds = [c for c in saved if c in TURNING_DRESSUPS]
        try:
            return cam_menu(self, recipient)
        finally:
            if turning and saved is not None:
                self.dressupcmds = saved

    ContextMenu.offers_turning_dressups = True
    type(workbench).ContextMenu = ContextMenu


offer_turning_dressups()


def turning_feed_squawks(sanity):
    """CAM Sanity squawks for turning tool controllers with no vertical feed: CAUTION for
    a turning insert, WARNING for a drill or grooving blade (they plunge with it)."""
    import PathTurnScripts.PathTurnBase as PathTurnBase
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
            note = ("{}: No vertical feedrate. A drill or a grooving or parting blade plunges with it: set one. "
                    "Falling back to horizontal feedrate of {}").format(where, tc.HorizFeed.UserString)
            kind = "WARNING"
        else:
            note = "{}: No vertical feedrate, falling back to horizontal feedrate of {}".format(where, tc.HorizFeed.UserString)
            kind = "CAUTION"
        squawks.append(sanity.squawk("CAMSanity", note, squawkType=kind))
    return squawks


def add_turning_feed_checks():
    """CAM Sanity (the post dialog's warnings and the Sanity report) gets the
    turning operations' feed checks."""
    try:
        import Path.Main.Sanity.Sanity as Sanity
    except Exception:
        return
    cls = Sanity.CAMSanity
    original = cls.get_all_squawks
    if getattr(original, "turning_feeds", False):
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

    get_all_squawks.turning_feeds = True
    cls.get_all_squawks = get_all_squawks


add_turning_feed_checks()


def release_closed_button_boxes():
    """Patch Path.Op.Gui.Base.TaskPanel.cleanup to drop its reference to the dialog's
    button box before the widgets are deleted (a stale PySide wrapper otherwise)."""
    try:
        import Path.Op.Gui.Base as PathOpGui
    except Exception:
        return
    panel = PathOpGui.TaskPanel
    cleanup = panel.cleanup
    if getattr(cleanup, "releases_button_box", False):
        return

    def release(self, resetEdit):
        self.buttonBox = None
        for page in list(getattr(self, "featurePages", []) or []):
            point = getattr(page, "getPoint", None)
            if point is not None and hasattr(point, "buttonBox"):
                point.buttonBox = None
        return cleanup(self, resetEdit)

    release.releases_button_box = True
    panel.cleanup = release


release_closed_button_boxes()


def feeds_speeds_for_inserts():
    """CAM's Feeds & Speeds dialog (the Tool Controller's button) works out
    the rpm for a turning tool at the stock's diameter, not the insert's."""
    try:
        from PathTurnScripts import TurnFeedsSpeeds
        TurnFeedsSpeeds.install_dialog_hook()
    except Exception as e:
        FreeCAD.Console.PrintLog("TurningAddon: Feeds & Speeds hook failed: {}\n".format(e))


feeds_speeds_for_inserts()


def add_turning_toolbar():
    """Patch CAMWorkbench.Initialize to add a Turning toolbar with the menu's commands,
    so the toolbar belongs to the CAM workbench and only shows there."""
    try:
        workbench = FreeCADGui.getWorkbench("CAMWorkbench")
    except Exception:
        return
    cam_initialize = getattr(type(workbench), "Initialize", None)
    if cam_initialize is None or getattr(cam_initialize, "adds_turning_toolbar", False):
        return

    def Initialize(self):
        cam_initialize(self)
        # the addon's shapes already in CAM's store, as the addon has them now
        try:
            from PathTurnScripts import TurnAssets
            TurnAssets.refresh_installed_shapes()
        except Exception as e:
            FreeCAD.Console.PrintLog("TurningAddon: refreshing the tool shapes failed: {}\n".format(e))
        try:
            self.appendToolbar(TOOLBAR, COMMANDS)
        except Exception as e:
            FreeCAD.Console.PrintWarning("Turning: could not add the Turning toolbar: {}\n".format(e))

    Initialize.adds_turning_toolbar = True
    type(workbench).Initialize = Initialize


add_turning_toolbar()
