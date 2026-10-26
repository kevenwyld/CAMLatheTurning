# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Groove operation."""

import FreeCAD
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnChamfer as PathTurnChamfer
import Path.Op.Gui.Base as PathOpGui

from PySide import QtCore


class TaskPanelOpPage(PathTurnBaseGui.TaskPanelTurnBase):
    '''Page controller class for the Turn Groove operation.'''

    def setOpFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        # a grooving insert reaches into grooves by itself
        self.form.allowGrooving.setVisible(False)


Command = PathOpGui.SetupOperation('TurnChamfer',
                                   PathTurnChamfer.Create,
                                   TaskPanelOpPage,
                                   'CAM-TurnChamfer',
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnChamfer", "Turn Chamfer"),
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnChamfer",
                                                            "Chamfers or fillets the selected corners (circular edges)"),
                                   PathTurnChamfer.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathTurnChamferGui... done\n")
