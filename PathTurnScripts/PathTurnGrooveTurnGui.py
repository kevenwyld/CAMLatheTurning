# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Groove-Turn operation."""

import FreeCAD
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnGrooveTurn as PathTurnGrooveTurn
import Path.Op.Gui.Base as PathOpGui

from PySide import QtCore


class TaskPanelOpPage(PathTurnBaseGui.TaskPanelTurnBase):
    '''Page controller class for the Turn Groove-Turn operation.'''

    def setOpFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        # a grooving insert reaches into grooves by itself
        self.form.allowGrooving.setVisible(False)


Command = PathOpGui.SetupOperation('TurnGrooveTurn',
                                   PathTurnGrooveTurn.Create,
                                   TaskPanelOpPage,
                                   'CAM-TurnGrooveTurn',
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnGrooveTurn", "Turn Groove-Turn"),
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnGrooveTurn",
                                                            "Groove turning along the whole profile with a grooving "
                                                            "or full radius insert, in both directions"),
                                   PathTurnGrooveTurn.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathTurnGrooveTurnGui... done\n")
