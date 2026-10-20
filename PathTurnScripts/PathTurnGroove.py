# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Groove: grooving, parting-off style plunging and both-direction
finishing with a grooving or parting insert (Grooving / Parting Insert
shape). The path comes from liblathe's GrooveOP, which drop-cuts the blade's
actual cutting edge (flat bottom, corner radii, straight flanks) against the
part, so it can follow a groove's walls in both directions.
"""

import FreeCAD
import Path
import PathTurnScripts.PathTurnBase as PathTurnBase
import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers
from PySide import QtCore

import liblathe.op.groove as LLG


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTurnGroove(PathTurnBase.ObjectOp):
    '''Proxy class for turning groove operations.'''

    uses_grooving_tool = True

    def opFeatures(self, obj):
        '''Turning features plus base geometry: the selection sets the Z range.'''
        PathOp = PathTurnBase.PathOp
        return (super().opFeatures(obj)
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges | PathOp.FeatureBaseModels)

    def initOperation(self, obj):
        super().initOperation(obj)
        self.add_groove_properties(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        if not hasattr(obj, "FinishAllowance"):
            self.add_groove_properties(obj)

    def add_groove_properties(self, obj):
        obj.addProperty("App::PropertyLength", "FinishAllowance", "Turn Path",
                        translate("TurnPath", "Material the roughing plunges leave for the finish passes (per side)"))
        obj.FinishAllowance = 0.2

    def op_generate_gcode(self, obj, tool):
        '''Generate the path with liblathe's GrooveOP from the grooving insert's parameters.'''
        op = LLG.GrooveOP()
        op.set_params(self.getProps(obj))
        op.set_params({
            'groove_width': tool.Width.Value,
            'corner_radius': tool.CornerRadius.Value,
            'cutting_depth': tool.CuttingDepth.Value if hasattr(tool, "CuttingDepth") else 0,
            'turning_depth': tool.TurningDepth.Value if hasattr(tool, "TurningDepth") else 0,
            'finish_allowance': obj.FinishAllowance.Value,
        })
        op.add_stock(PathTurnHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox))
        op.add_part_edges(self.part_outline)

        for command in op.get_gcode():
            self.commandlist.append(Path.Command(command.get_movement(), command.get_params()))
        for warning in getattr(op, "warnings", []):
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))

    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = job.Stock.Shape.BoundBox.ZMin
        obj.FinishPasses = 1

    def opUpdateDepths(self, obj):
        # the selected geometry sets the Z range, otherwise the whole stock
        self.update_depths_from_base(obj)


def SetupProperties():
    return ["StepOver", "FinishPasses", "FinishAllowance"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnGroove operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnGroove(obj, name, parentJob)
    return obj
