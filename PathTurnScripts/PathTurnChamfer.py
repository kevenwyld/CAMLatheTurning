# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Chamfer: a chamfer or a fillet at chosen corners of the part.

Select the corners' circular edges (circles round the spindle axis) on the
Edges page; each gets a chamfer (equal legs: 45 degrees at a square corner)
or a fillet (an arc tangent to both edges) of the given size, cut by a short
contour pass round it with nose radius compensation. Only sharp outside
corners between two straight edges can be chamfered or filleted; others are
reported and left alone. For every sharp corner at once, use Break edges on
Turn Rough, Turn Profile or Turn Face instead.
"""
import math

import FreeCAD
import Part
import PathTurnScripts.PathTurnBase as PathTurnBase
import liblathe.op.chamfer as LLC

from PySide import QtCore

__title__ = "Path Turn Chamfer Operation"
__doc__ = "A chamfer or fillet at chosen corners."

KINDS = ["Chamfer", "Fillet"]


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTurnChamfer(PathTurnBase.ObjectOp):
    '''Proxy class for chamfering or filleting chosen corners.'''

    # the selection picks corners (circular edges), not a Z range
    selects_corners = True

    def opFeatures(self, obj):
        return super().opFeatures(obj) | PathTurnBase.PathOp.FeatureBaseEdges

    def initOperation(self, obj):
        super().initOperation(obj)
        self.add_corner_properties(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        self.add_corner_properties(obj)

    def add_corner_properties(self, obj):
        if not hasattr(obj, "CornerType"):
            obj.addProperty("App::PropertyEnumeration", "CornerType", "Chamfer", translate(
                "TurnPath", "Chamfer (equal legs: 45 degrees at a square corner) or Fillet (an arc tangent to both "
                            "edges)"))
            obj.CornerType = KINDS
        if not hasattr(obj, "CornerSize"):
            obj.addProperty("App::PropertyLength", "CornerSize", "Chamfer", translate(
                "TurnPath", "A chamfer's leg along each edge, or a fillet's radius"))
            obj.CornerSize = FreeCAD.Units.Quantity(0.5, FreeCAD.Units.Length)

    # the whole part: the selection only says which corners
    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = job.Stock.Shape.BoundBox.ZMin

    def opUpdateDepths(self, obj):
        obj.OpStartDepth = obj.OpStockZMax
        obj.OpFinalDepth = obj.OpStockZMin

    def selected_corners(self, obj):
        '''(radius, z) of each selected circular edge round the spindle axis.'''
        found, other = [], 0
        for base, subs in (getattr(obj, "Base", None) or []):
            for sub in subs:
                if not sub.startswith("Edge"):
                    other += 1
                    continue
                edge = base.Shape.getElement(sub)
                curve = edge.Curve
                if (isinstance(curve, Part.Circle) and abs(abs(curve.Axis.z) - 1) < 1e-6
                        and math.hypot(curve.Center.x, curve.Center.y) < 1e-3):
                    found.append((curve.Radius, curve.Center.z))
                else:
                    other += 1
        return found, other

    def op_generate_gcode(self, obj, turnTool):
        corners, other = self.selected_corners(obj)
        if other:
            FreeCAD.Console.PrintWarning("{}: {} selected item(s) are not circular edges round the spindle axis, "
                                         "and are ignored\n".format(obj.Label, other))
        if not corners:
            raise RuntimeError(translate('PathTurn', "Select the circular edges (the corners) to chamfer or fillet"))
        kind = "fillet" if obj.CornerType == "Fillet" else "chamfer"
        op = LLC.ChamferOP()
        op.set_params(self.getProps(obj))
        op.set_params({'corners': [(r, z, kind, obj.CornerSize.Value) for r, z in corners]})
        op.add_stock(self.lathe_stock_box())
        op.add_part_edges(self.part_outline)
        op.add_tool(turnTool)
        code = op.get_gcode()
        self.report_lathe_warnings(obj, op)
        self.commandlist.extend(self.lathe_commands(code))


def SetupProperties():
    return ["CornerType", "CornerSize"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a Turn Chamfer operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnChamfer(obj, name, parentJob)
    return obj
