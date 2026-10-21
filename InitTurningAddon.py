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

import FreeCADGui

# register the ISO turning-insert toolbit shape
from PathTurnScripts import TurnToolShapes  # noqa: F401

# import all turning operations
from PathTurnScripts import PathTurnFaceGui  # noqa: F401
from PathTurnScripts import PathTurnGrooveGui  # noqa: F401
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
COMMANDS = ['CAM_TurnFace', 'CAM_TurnRough', 'CAM_TurnProfile', 'CAM_TurnGroove', 'CAM_TurnThread', 'CAM_TurnPartoff',
            'CAM_TurnToolHelper',
            'CAM_TurnInstallTools']

# Existing CAM command to insert after. It only exists in the CAM workbench's
# menu, so the manipulator is a no-op in every other workbench.
ANCHOR = 'CAM_Pocket3D'


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
