# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 Daniel Wood <s.d.wood.82@gmail.com>                *
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

import FreeCAD
import Path
import PathTurnScripts.PathTurnBase as PathTurnBase
import PathTurnScripts.TurnFeedsSpeeds as TurnFeedsSpeeds
from PySide import QtCore

import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers

import liblathe.op.profile as LLP

__title__ = "Path Turn Profile Operation"
__author__ = "dubstar-04 (Daniel Wood)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Class implementation for turning profiling operations."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTurnProfile(PathTurnBase.ObjectOp):
    '''Proxy class for turning profile operations.'''
    # CAM's feeds & speeds op type (constant surface speed)
    css_op_type = TurnFeedsSpeeds.OP_TYPE_FINISHING

    uses_pass_retract = True
    uses_break_edges = True
    uses_pass_lead_in = True

    turns_to_min_diameter = True
    supports_internal = True

    def initOperation(self, obj):
        super().initOperation(obj)
        add_spring_pass_property(obj)
        add_finish_properties(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        if not hasattr(obj, "SpringPass"):
            add_spring_pass_property(obj)
        if not hasattr(obj, "FinishStepOver"):
            # the finish passes used to be spaced by Step Over
            add_finish_properties(obj, obj.StepOver.Value)

    def opFeatures(self, obj):
        '''Turning features plus base geometry: the selected faces, edges and
        whole objects (e.g. a sketch or wire) set the Z range.'''
        PathOp = PathTurnBase.PathOp
        return (super().opFeatures(obj)
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges | PathOp.FeatureBaseModels)

    def op_generate_gcode(self, obj, turnTool):
        '''
        Generate GCode for the op
        '''
        profileOP = LLP.ProfileOP()
        profileOP.set_params(self.getProps(obj))
        profileOP.set_params({'spring_pass': obj.SpringPass})

        stockBoundbox = self.lathe_stock_box()
        profileOP.add_stock(stockBoundbox)

        profileOP.add_part_edges(self.part_outline)
        profileOP.add_tool(turnTool)

        PathCode = profileOP.get_gcode()
        self.report_lathe_warnings(obj, profileOP)
        self.report_broken_edges(obj, profileOP)
        self.show_lead_in(obj, profileOP)
        self.commandlist.extend(self.lathe_commands(PathCode))

    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = job.Stock.Shape.BoundBox.ZMin
        print('opSetDefaultValues:', obj.OpStartDepth.Value, obj.OpFinalDepth.Value)

    def opUpdateDepths(self, obj):
        # the selected geometry sets the Z range, otherwise the whole stock
        self.update_depths_from_base(obj)


def add_spring_pass_property(obj):
    obj.addProperty("App::PropertyBool", "SpringPass", "Turn Path",
                    translate("TurnPath", "Repeat the last finish pass once more, with no step over"))
    obj.SpringPass = False


def add_finish_properties(obj, step_over=0.5):
    obj.addProperty("App::PropertyLength", "FinishStepOver", "Turn Path",
                    translate("TurnPath", "Spacing of the finish passes"))
    obj.FinishStepOver = FreeCAD.Units.Quantity(step_over, FreeCAD.Units.Length)
    obj.addProperty("App::PropertyBool", "FinishFrontFace", "Turn Path",
                    translate("TurnPath", "Also finish the front face (normally left to Turn Face)"))
    obj.FinishFrontFace = False


def SetupProperties():
    setup = []
    setup.append("StepOver")
    setup.append("FinishPasses")
    setup.append("AllowGrooving")
    setup.append("StockToLeaveX")
    setup.append("StockToLeaveZ")
    setup.append("SpringPass")
    setup.append("FinishStepOver")
    return setup


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnProfile operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnProfile(obj, name, parentJob)
    return obj
