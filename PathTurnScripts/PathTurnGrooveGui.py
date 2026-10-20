# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Groove operation."""

import FreeCAD
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnGroove as PathTurnGroove
import Path.Op.Gui.Base as PathOpGui

from PySide import QtCore


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
