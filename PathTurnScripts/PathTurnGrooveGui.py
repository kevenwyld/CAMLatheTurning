# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Groove operation."""

import FreeCAD
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnGroove as PathTurnGroove
import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.Selection as PathSelection

from PySide import QtCore


# CAM's selection gates are looked up in a fixed table of operation names
# (Path.Op.Gui.Selection.select) that only lists the original four turning
# operations, so editing a TurnGroove raised KeyError: 'TurnGroove'. Send it to
# the same turning selection gate as the others.
if not getattr(PathSelection.select, "_turn_groove", False):
    _cam_select = PathSelection.select

    def _select(op):
        if op == "TurnGroove":
            return PathSelection.turnselect
        return _cam_select(op)

    _select._turn_groove = True
    PathSelection.select = _select


class TaskPanelOpPage(PathTurnBaseGui.TaskPanelTurnBase):
    '''Page controller class for the Turn Groove operation.'''

    def setOpFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        pass


Command = PathOpGui.SetupOperation('TurnGroove',
                                   PathTurnGroove.Create,
                                   TaskPanelOpPage,
                                   'CAM-TurnGroove',
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnGroove", "Turn Groove"),
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnGroove",
                                                            "Grooves, plunges and finishes in both directions "
                                                            "with a grooving or parting insert"),
                                   PathTurnGroove.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathTurnGrooveGui... done\n")
