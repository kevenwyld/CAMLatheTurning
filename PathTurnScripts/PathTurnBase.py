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
import Part
import Path
import Path.Log as PathLog
import Path.Op.Base as PathOp
import PathScripts.PathUtils as PathUtils
# import PathScripts.PathGeom as PathGeom

from PySide import QtCore

if FreeCAD.GuiUp:
    import FreeCADGui

from liblathe.base.point import Point
from liblathe.base.segment import Segment
from liblathe.base.tool import Tool

__title__ = "Path Turn Base Operation"
__author__ = "dubstar-04 (Daniel Wood)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Base class implementation for turning operations."


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


class ObjectOp(PathOp.ObjectOp):
    '''Base class for proxy objects of all turning operations.'''

    def opFeatures(self, obj):
        '''opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.'''
        return PathOp.FeatureDiameters | PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureCoolant

    def initOperation(self, obj):
        '''initOperation(obj)'''

        obj.addProperty("App::PropertyLength", "StepOver", "Turn Path", translate("TurnPath", "Operation Stepover"))
        obj.addProperty("App::PropertyInteger", "FinishPasses", "Turn Path", translate("TurnPath", "Number of Finish Passes"))
        obj.addProperty("App::PropertyFloat", "StockToLeave", "Turn Path", translate("TurnPath", "Distance for stock to leave uncut"))
        obj.addProperty("App::PropertyBool", "AllowGrooving", "Turn Path", translate("TurnPath", "Minimum Diameter for Operation"))

        obj.StepOver = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length)
        obj.FinishPasses = 2
        obj.StockToLeave = 0

    def depths_from_base(self, obj):
        '''
        Z extent of the selected base geometry as (start depth, final depth),
        or None when nothing is selected. Selecting faces confines Rough and
        Profile to the Z range of those faces.
        '''
        base = getattr(obj, "Base", None)
        if not base:
            return None
        zmax = zmin = None
        for base_obj, subs in base:
            for sub in (subs or [""]):
                try:
                    shape = base_obj.Shape.getElement(sub) if sub else base_obj.Shape
                except Exception:
                    continue
                bb = shape.BoundBox
                zmax = bb.ZMax if zmax is None else max(zmax, bb.ZMax)
                zmin = bb.ZMin if zmin is None else min(zmin, bb.ZMin)
        if zmax is None:
            return None
        return zmax, zmin

    def update_depths_from_base(self, obj):
        '''Set OpStartDepth / OpFinalDepth from the selection, or the stock.'''
        depths = self.depths_from_base(obj)
        if depths:
            obj.OpStartDepth, obj.OpFinalDepth = depths
        else:
            obj.OpStartDepth = obj.OpStockZMax
            obj.OpFinalDepth = obj.OpStockZMin

    def opExecute(self, obj):
        '''opExecute(obj) ... processes all Base features
        '''
        PathLog.track()
        self.tool = None
        self.minDia = obj.MinDiameter.Value
        self.maxDia = obj.MaxDiameter.Value

        if self.minDia >= self.maxDia:
            raise RuntimeError(translate('PathTurn', "Minimum diameter is equal or greater than maximum diameter"))

        if obj.StartDepth.Value <= obj.FinalDepth.Value:
            raise RuntimeError(translate('PathTurn', "Start depth is equal or less than final depth"))

        self.startOffset = 0
        self.endOffset = 0
        self.allowGrooving = obj.AllowGrooving
        self.stepOver = obj.StepOver.Value
        self.finishPasses = obj.FinishPasses
        self.stockToLeave = obj.StockToLeave

        # Clear any existing gcode
        obj.Path.Commands = []

        print("Process Geometry")
        self.stock_silhoutte = self.get_stock_silhoutte(obj)
        self.part_outline = self.get_part_outline()
        self.generate_gcode(obj)

    def getProps(self, obj):
        parentJob = PathUtils.findParentJob(obj)

        props = {}
        props['min_dia'] = self.minDia
        props['extra_dia'] = self.maxDia - self.stock.Shape.BoundBox.XLength
        props['start_offset'] = self.startOffset
        props['end_offset'] = self.endOffset
        props['allow_grooving'] = self.allowGrooving
        props['step_over'] = self.stepOver
        props['finish_passes'] = self.finishPasses
        props['stock_to_leave'] = self.stockToLeave
        props['hfeed'] = obj.ToolController.HorizFeed.Value
        props['vfeed'] = obj.ToolController.VertFeed.Value
        props['clearance'] = parentJob.SetupSheet.SafeHeightOffset.Value
        return props

    def get_stock_silhoutte(self, obj):
        '''
        Get Stock Silhoutte

        The plane covers the whole stock. The operation's Z limits are passed
        to liblathe separately, as offsets from the stock ends:
            start_offset = StartDepth - stock ZMax  (negative: inside the stock)
            end_offset   = stock ZMin - FinalDepth  (negative: short of the stock end)
        so liblathe's window runs from StartDepth to FinalDepth.
        '''
        stockBB = self.stock.Shape.BoundBox
        stock_z_pos = stockBB.ZMax

        self.startOffset = obj.StartDepth.Value - stockBB.ZMax
        self.endOffset = stockBB.ZMin - obj.FinalDepth.Value

        stock_plane_length = stockBB.ZLength
        stock_plane_width = stockBB.XLength / 2
        stock_plane = Part.makePlane(stock_plane_length, stock_plane_width,
                                     FreeCAD.Vector(-stock_plane_width, 0, stock_z_pos), FreeCAD.Vector(0, -1, 0))
        return stock_plane

    def get_part_outline(self):
        '''
        Get Part Outline
        '''
        # TODO: Revisit the edge extraction and find a more elegant method
        model = self.model[0].Shape
        # get a section through the part origin on the XZ Plane
        sections = Path.Area().add(model).makeSections(mode=0, heights=[0.0], project=True, plane=self.stock_silhoutte)
        part_silhoutte = sections[0].setParams(Offset=0.0).getShape()
        # get an offset section larger than the part section
        part_bound_face = sections[0].setParams(Offset=0.1).getShape()

        # ensure the cutplane is larger than the part or segments will be missed
        modelBB = model.BoundBox
        plane_length = modelBB.ZLength * 1.5
        plane_width = (modelBB.XLength / 2) * 1.5
        z_ref = modelBB.ZMax + (plane_length - modelBB.ZLength) / 2

        # create a plane larger than the part
        cut_plane = Part.makePlane(plane_length, plane_width, FreeCAD.Vector(-plane_width, 0, z_ref), FreeCAD.Vector(0, -1, 0))
        # Cut the part section from the cut plane
        path_area = cut_plane.cut(part_silhoutte)

        # collect the outline edges that lie on the part
        items = []
        for edge in path_area.Edges:
            edge_in = True
            for vertex in edge.Vertexes:
                if not part_bound_face.isInside(vertex.Point, 0.1, True):
                    edge_in = False
            if not edge_in:
                continue

            p0 = edge.Vertexes[0].Point
            p1 = edge.Vertexes[-1].Point
            item = {"p0": (p0.x, p0.z), "p1": (p1.x, p1.z), "mid": None, "angle": 0}
            if isinstance(edge.Curve, Part.Circle):
                m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                item["mid"] = (m.x, m.z)
                item["angle"] = abs(edge.LastParameter - edge.FirstParameter)
            items.append(item)

        # FreeCAD returns the edges in arbitrary order and direction; liblathe
        # needs one continuous chain from the front (X=0, max Z) to the back.
        chain, unchained = chain_profile(items)
        if unchained:
            FreeCAD.Console.PrintWarning(
                "Turning: %d outline edge(s) are not connected to the main profile and were ignored\n" % unchained)

        part_segments = []
        for s, e, signed_angle in chain:
            seg = Segment(Point(s[0], 0, s[1]), Point(e[0], 0, e[1]))
            if signed_angle:
                seg.set_bulge(signed_angle)
            part_segments.append(seg)

        # Debug: uncomment to show the extracted profile in the document
        # Part.show(Part.makePolygon([FreeCAD.Vector(s[0], 0, s[1]) for s, e, a in chain] +
        #                            [FreeCAD.Vector(chain[-1][1][0], 0, chain[-1][1][1])]), 'TurnProfile')
        return part_segments

    def generate_gcode(self, obj):
        '''
        Base function to generate gcode for the OP by writing path command to self.commandlist
        Calls operations op_generate_gcode.
        '''
        opTool = obj.ToolController.Tool

        # only toolbits are supported
        #if isinstance(opTool, Path.Tool):
        #    raise RuntimeError(translate('PathTurn', "Path Turn: Legacy Tools Not Supported "))

        # create a liblathe tool and assign the toolbit parameters
        turnTool = Tool()

        # TODO: set some sensible default values or raise error if attribute not available

        if hasattr(opTool, "TipAngle"):
            turnTool.set_tip_angle(opTool.TipAngle.Value)

        if hasattr(opTool, "EdgeLength"):
            turnTool.set_edge_length(opTool.EdgeLength.Value)

        if hasattr(opTool, "TipRadius"):
            turnTool.set_nose_radius(opTool.TipRadius.Value)

        if hasattr(opTool, "Rotation"):
            turnTool.set_rotation(opTool.Rotation.Value)

        self.op_generate_gcode(obj, turnTool)

    def op_generate_gcode(self, obj, turnTool):
        '''op_generate_gcode(obj) ... overwrite to set initial default values.
        Called after the receiver has been fully created with all properties.
        Should be overwritten by subclasses.'''
        pass  # pylint: disable=unnecessary-pass


def chain_profile(items, tol=1e-4):
    """
    Order and orient outline edges into one continuous chain for liblathe.

    items: list of dicts with keys
        p0, p1 : (x, z) end points, in the edge's own (arbitrary) direction
        mid    : (x, z) point at the middle of the edge, or None for lines
        angle  : included angle in radians for arcs (positive), 0 for lines
    Returns a list of (start, end, signed_angle) running from the front of
    the part (X=0, max Z) to the back, with arc angles signed in liblathe's
    convention (positive = anticlockwise in the Z-horizontal / X-vertical view).
    Also returns the number of edges that couldn't be chained.
    """
    def close(a, b):
        return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol

    remaining = list(items)
    ends = [it["p0"] for it in items] + [it["p1"] for it in items]
    on_axis = [p for p in ends if abs(p[0]) < tol]
    start = max(on_axis or ends, key=lambda p: p[1])

    out = []
    current = start
    while remaining:
        for i, it in enumerate(remaining):
            if close(it["p0"], current):
                s, e = it["p0"], it["p1"]
                break
            if close(it["p1"], current):
                s, e = it["p1"], it["p0"]
                break
        else:
            break  # no connected edge: chain ends here
        remaining.pop(i)

        signed = 0.0
        if it["mid"] is not None and it["angle"]:
            # u = Z (horizontal), v = X (vertical); cross < 0 => anticlockwise
            du1, dv1 = e[1] - s[1], e[0] - s[0]
            du2, dv2 = it["mid"][1] - s[1], it["mid"][0] - s[0]
            cross = du1 * dv2 - dv1 * du2
            signed = it["angle"] if cross < 0 else -it["angle"]
        # snap near-axis X to exactly 0 (liblathe validate() checks X == 0)
        s = (0.0 if abs(s[0]) < tol else s[0], s[1])
        e = (0.0 if abs(e[0]) < tol else e[0], e[1])
        out.append((s, e, signed))
        current = e

    return out, len(remaining)
