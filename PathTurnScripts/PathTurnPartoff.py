# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2020 Daniel Wood <s.d.wood.82@gmail.com>                *
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
from PySide import QtCore

import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers

import liblathe.op.partoff as LLP

__title__ = "Path Turn Part Operation"
__author__ = "dubstar-04 (Daniel Wood)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Class implementation for turning profiling operations."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTurnPart(PathTurnBase.ObjectOp):
    '''Proxy class for turning Part operations.'''

    # parting is done with a parting or grooving insert (its real width)
    uses_grooving_tool = True

    def opFeatures(self, obj):
        '''Turning features plus base geometry: a selection sets where to part off.'''
        PathOp = PathTurnBase.PathOp
        return (super().opFeatures(obj)
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges | PathOp.FeatureBaseModels)

    def initOperation(self, obj):
        super().initOperation(obj)
        self.add_partoff_properties(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        if not hasattr(obj, "Overtravel"):
            self.add_partoff_properties(obj)

    def add_partoff_properties(self, obj):
        obj.addProperty("App::PropertyLength", "Overtravel", "Turn Path",
                        translate("TurnPath", "How far past the centreline the blade goes, so no pip is left"))
        obj.Overtravel = FreeCAD.Units.Quantity(0.2, FreeCAD.Units.Length)

    def op_generate_gcode(self, obj, tool):
        '''Generate the parting plunge from the parting insert's parameters.'''
        PartOP = LLP.PartoffOP()
        PartOP.set_params(self.getProps(obj))

        def length(name, default=0.0):
            return getattr(tool, name).Value if hasattr(tool, name) else default

        width = tool.Width.Value
        PartOP.set_params({
            'groove_width': width,
            'corner_radius': length("CornerRadius", width / 2),
            'cutting_depth': length("GroovingDepth", length("CuttingDepth")),
            'overtravel': obj.Overtravel.Value,
        })

        stockBoundbox = PathTurnHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox)
        PartOP.add_stock(stockBoundbox)
        PartOP.add_part_edges(self.part_outline)

        for command in PartOP.get_gcode():
            self.commandlist.append(Path.Command(command.get_movement(), command.get_params()))
        for warning in getattr(PartOP, "warnings", []):
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))

    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = self.part_back_face(obj, job)

    def opUpdateDepths(self, obj):
        # part off at the back of the selection, or else of the model: Final
        # Depth is where the part's back face ends up
        obj.OpStartDepth = obj.OpStockZMax
        selected = self.depths_from_base(obj)
        obj.OpFinalDepth = selected[1] if selected else self.part_back_face(obj)

    def part_back_face(self, obj, job=None):
        job = job or PathUtils_findParentJob(obj)
        models = job.Model.Group if job is not None and hasattr(job, "Model") else []
        if models:
            return min(m.Shape.BoundBox.ZMin for m in models if hasattr(m, "Shape"))
        return obj.OpStockZMin


def PathUtils_findParentJob(obj):
    import PathScripts.PathUtils as PathUtils
    return PathUtils.findParentJob(obj)


def SetupProperties():
    return ["Overtravel"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnPart operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnPart(obj, name, parentJob)
    return obj
