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

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join(__dir__, 'Gui/Resources/Icons')

# The commands' pixmaps are named after the icon files (e.g. 'CAM-TurnFace'),
# so adding the folder to the icon search path lets FreeCAD resolve them.
FreeCADGui.addIconPath(iconPath)

# Turning commands, in menu order
COMMANDS = ['CAM_TurnFace', 'CAM_TurnDrill', 'CAM_TurnRough', 'CAM_TurnProfile', 'CAM_TurnChamfer', 'CAM_TurnGroove', 'CAM_TurnGrooveTurn', 'CAM_TurnThread', 'CAM_TurnPartoff',
            'CAM_TurnToolHelper',
            'CAM_TurnInstallTools']

# Existing CAM command to insert after. It only exists in the CAM workbench's
# menu, so the manipulator is a no-op in every other workbench.
ANCHOR = 'CAM_Pocket3D'
TOOLBAR = 'Turning'


class TurningMenuManipulator:
    """
    Adds the turning commands to the CAM menu.

    FreeCAD rebuilds a workbench's menus every time it is activated and
    removes anything it didn't put there itself, which is why the old
    Qt-level submenu disappeared after switching workbenches. A workbench
    manipulator is applied by FreeCAD during every rebuild, so the entries
    persist.
    """

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
    """
    Let CAM treat the turning operations as operations everywhere it asks.

    CAM's Path.Dressup.Utils.isOp() decides by the module of an object's
    proxy ("Path.Op..." or "Path.Dressup..."), not by its class, so an
    addon's operations, though they derive from CAM's ObjectOp, are left
    out: the context menu's Active toggle, Dressup, Array / Copy, Inspect
    and Post Selected entries, and dressups and Simple Copy refuse them.
    Extend it to accept the turning operations too. CAM always calls it
    through the module, so replacing the function there reaches every use.

    TODO: upstream, isOp() should check isinstance(obj.Proxy,
    Path.Op.Base.ObjectOp) (and the dressup base); then drop this.
    """
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
    """
    For a selection of turning operations, CAM's context menu offers only
    the dressups that make sense on a lathe path. CAM's workbench builds
    the Dressup submenu from its dressupcmds list; while it builds the menu
    for turning operations, that list is the shorter one.
    """
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
    """
    The turning operations' feed checks, as CAM Sanity squawks: a tool
    controller with no vertical feed, used by a turning operation. The
    operations then plunge and enter the cut at the horizontal feed: a
    CAUTION for a turning insert; a WARNING for a drill or a grooving or
    parting blade, which plunge with it (as near an error as CAM's squawks
    go). Turn Thread is fed by the pitch and is not checked.
    """
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


def add_turning_toolbar():
    """
    A Turning toolbar in the CAM workbench, with the same commands as the
    menu. A workbench declares its toolbars in Initialize(), which FreeCAD
    runs once, the first time it is activated: CAM's is extended to add this
    one too, so the toolbar belongs to the CAM workbench and only shows there.
    """
    try:
        workbench = FreeCADGui.getWorkbench("CAMWorkbench")
    except Exception:
        return
    cam_initialize = getattr(type(workbench), "Initialize", None)
    if cam_initialize is None or getattr(cam_initialize, "adds_turning_toolbar", False):
        return

    def Initialize(self):
        cam_initialize(self)
        try:
            self.appendToolbar(TOOLBAR, COMMANDS)
        except Exception as e:
            FreeCAD.Console.PrintWarning("Turning: could not add the Turning toolbar: {}\n".format(e))

    Initialize.adds_turning_toolbar = True
    type(workbench).Initialize = Initialize


add_turning_toolbar()
