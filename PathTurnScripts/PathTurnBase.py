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


def is_threading_tool(tool):
    '''True for a threading insert (Threading shape).'''
    return hasattr(tool, "ProfileAngle")


def is_grooving_tool(tool):
    '''True for a grooving, parting or full radius insert (Grooving / Full Radius shapes).'''
    return (hasattr(tool, "Width") and not hasattr(tool, "TipAngle")
            and any(hasattr(tool, p) for p in ("GroovingDepth", "CuttingDepth", "CornerRadius")))


# Min / Max Diameter are worked out unless set by hand: (switch, value, tooltip)
DIAMETER_SWITCHES = (
    ("SetMinDiameter", "MinDiameter",
     "Set Min Diameter by hand: Rough, Profile and Turn Groove then turn to it across the Z range (into the model "
     "where it is bigger), Face and Partoff stop at it (e.g. a bore). Otherwise no inner limit: the op follows the part"),
    ("SetMaxDiameter", "MaxDiameter",
     "Set Max Diameter by hand: where the material starts (e.g. a surface already turned smaller). Otherwise the stock"),
)

STOCK_X_TIP = ("Material to leave radially, per side (on diameters). Negative cuts under the model's size, e.g. "
               "-0.075 to turn a 12 mm model to 11.85, a thread's major diameter turned to its tolerance")
STOCK_Z_TIP = ("Material to leave axially (on faces and shoulders). Negative cuts under the model's size, "
               "moving faces into the part")


class ObjectOp(PathOp.ObjectOp):

    # operations that work with a grooving insert instead of a turning insert
    uses_grooving_tool = False
    # operations that work with a threading insert
    uses_threading_tool = False
    # operations for which a Min Diameter set by hand is a diameter to turn
    # to across the Z range (into the model where it is bigger); for the
    # others (Face, Partoff, Thread) it stays their inner limit (e.g. a bore)
    turns_to_min_diameter = False

    '''Base class for proxy objects of all turning operations.'''

    def opFeatures(self, obj):
        '''opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.'''
        return PathOp.FeatureDiameters | PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureCoolant

    def initOperation(self, obj):
        '''initOperation(obj)'''

        obj.addProperty("App::PropertyLength", "StepOver", "Turn Path", translate("TurnPath", "Operation Stepover"))
        obj.addProperty("App::PropertyInteger", "FinishPasses", "Turn Path", translate("TurnPath", "Number of Finish Passes"))
        self.add_stock_properties(obj)
        self.add_diameter_switches(obj)
        obj.addProperty("App::PropertyBool", "AllowGrooving", "Turn Path",
                        translate("TurnPath", "Let the tool follow the part into grooves and undercuts as far as its "
                                              "cutting angle allows"))

        obj.StepOver = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length)
        obj.FinishPasses = 2

    def add_diameter_switches(self, obj, migrate=False):
        '''The Set switches for Min / Max Diameter. On an older document a
        Min Diameter above 0, or a Max Diameter other than the stock's, was
        set by hand.'''
        for switch, prop, tip in DIAMETER_SWITCHES:
            if hasattr(obj, switch):
                continue
            obj.addProperty("App::PropertyBool", switch, "Diameters", translate("TurnPath", tip))
            value = getattr(getattr(obj, prop, None), "Value", 0.0) or 0.0
            hand = False
            if migrate and prop == "MinDiameter":
                hand = value > 1e-6
            elif migrate and prop == "MaxDiameter":
                stock = self.stock_diameter(obj)
                # (within 0.01: bounding boxes of curved stock are not tight)
                hand = stock is not None and abs(value - stock) > 0.01
            setattr(obj, switch, hand)

    @staticmethod
    def stock_diameter(obj):
        try:
            job = PathUtils.findParentJob(obj)
            return job.Stock.Shape.BoundBox.XLength
        except Exception:
            return None

    def add_stock_properties(self, obj, value=0.0):
        '''Stock to leave, per side: X (radially, on diameters) and Z (axially, on faces).'''
        obj.addProperty("App::PropertyDistance", "StockToLeaveX", "Turn Path",
                        translate("TurnPath", STOCK_X_TIP))
        obj.addProperty("App::PropertyDistance", "StockToLeaveZ", "Turn Path",
                        translate("TurnPath", STOCK_Z_TIP))
        obj.StockToLeaveX = FreeCAD.Units.Quantity(value, FreeCAD.Units.Length)
        obj.StockToLeaveZ = FreeCAD.Units.Quantity(value, FreeCAD.Units.Length)

    def opOnDocumentRestored(self, obj):
        '''Migrate the single StockToLeave of earlier versions to X and Z, and
        X and Z from lengths (never negative) to distances (signed).'''
        super().opOnDocumentRestored(obj)
        if not hasattr(obj, "StockToLeaveX"):
            old = float(getattr(obj, "StockToLeave", 0.0) or 0.0)
            self.add_stock_properties(obj, old)
            if hasattr(obj, "StockToLeave"):
                obj.removeProperty("StockToLeave")
        self.add_diameter_switches(obj, migrate=True)
        for prop, tip in (("StockToLeaveX", STOCK_X_TIP), ("StockToLeaveZ", STOCK_Z_TIP)):
            if obj.getTypeIdOfProperty(prop) == "App::PropertyLength":
                value = getattr(obj, prop).Value
                expression = dict(obj.ExpressionEngine or []).get(prop)
                obj.removeProperty(prop)
                obj.addProperty("App::PropertyDistance", prop, "Turn Path", translate("TurnPath", tip))
                setattr(obj, prop, FreeCAD.Units.Quantity(value, FreeCAD.Units.Length))
                if expression:
                    obj.setExpression(prop, expression)

    def depths_from_base(self, obj):
        '''
        Z extent of the selected base geometry as (start depth, final depth),
        or None when nothing is selected. Selecting faces, edges or whole
        objects (e.g. a sketch or wire) confines Rough and Profile to the Z
        range they span.
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
        # worked out unless set by hand: Max Diameter the stock's, Min
        # Diameter none (0: the op follows the part); shown in the fields
        if not getattr(obj, "SetMaxDiameter", True):
            stock = self.stock_diameter(obj)
            if stock is not None and abs(obj.MaxDiameter.Value - stock) > 1e-9:
                obj.MaxDiameter = FreeCAD.Units.Quantity(stock, FreeCAD.Units.Length)
        if not getattr(obj, "SetMinDiameter", True) and obj.MinDiameter.Value != 0:
            obj.MinDiameter = FreeCAD.Units.Quantity(0.0, FreeCAD.Units.Length)
        self.minDia = obj.MinDiameter.Value
        self.maxDia = obj.MaxDiameter.Value

        if self.minDia >= self.maxDia:
            raise RuntimeError(translate('PathTurn', "Minimum diameter is equal or greater than maximum diameter"))

        # bounding boxes are padded by the modelling tolerance (~1e-7 mm), so a
        # flat face selected on the Z Range page gives a tiny positive range
        if obj.StartDepth.Value - obj.FinalDepth.Value <= 1e-4:
            if self.depths_from_base(obj):
                raise RuntimeError(translate('PathTurn',
                    "The selection has no length along Z (e.g. a single shoulder face or circular "
                    "edge): select geometry at two different Z positions, or set the depths"))
            raise RuntimeError(translate('PathTurn', "Start depth is equal or less than final depth"))

        self.startOffset = 0
        self.endOffset = 0
        self.allowGrooving = obj.AllowGrooving
        self.stepOver = obj.StepOver.Value
        self.finishPasses = obj.FinishPasses
        self.stockToLeaveX = obj.StockToLeaveX.Value
        self.stockToLeaveZ = obj.StockToLeaveZ.Value

        # Clear any existing gcode
        obj.Path.Commands = []

        print("Process Geometry")
        self.stock_silhoutte = self.get_stock_silhoutte(obj)
        self.part_outline = self.get_part_outline(self.turned_model(obj))
        self.generate_gcode(obj)
        self.warn_if_nothing_cut(obj)

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
        props['stock_to_leave'] = max(self.stockToLeaveX, self.stockToLeaveZ)
        props['stock_to_leave_x'] = self.stockToLeaveX
        props['stock_to_leave_z'] = self.stockToLeaveZ
        props['finish_step_over'] = obj.FinishStepOver.Value if hasattr(obj, "FinishStepOver") else 0.0
        props['face_front'] = bool(getattr(obj, "FinishFrontFace", False))
        props['hfeed'] = obj.ToolController.HorizFeed.Value
        # an unset (zero) vertical feed falls back to the horizontal feed
        props['vfeed'] = obj.ToolController.VertFeed.Value or obj.ToolController.HorizFeed.Value
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

    def turned_model(self, obj):
        '''
        The model as the operation is to leave it. With Min Diameter set by
        hand, Rough, Profile and Turn Groove turn to it across the Z range:
        one diameter there, cut into the model where it is bigger, left at
        Min Diameter where the model is smaller (as a milling op leaves a
        floor at its final depth). The outline they follow, and check their
        paths against, is then the target, arcs and all outside the range.
        '''
        model = self.model[0].Shape
        if not (self.turns_to_min_diameter and getattr(obj, "SetMinDiameter", False) and self.minDia > 0):
            return model
        z_lo, z_hi = obj.FinalDepth.Value, obj.StartDepth.Value
        if z_hi - z_lo <= 1e-6:
            return model
        r_in = self.minDia / 2
        r_out = max(model.BoundBox.XLength, model.BoundBox.YLength, self.maxDia) + 10.0
        if r_in >= r_out:
            return model
        base = FreeCAD.Vector(0, 0, z_lo)
        tube = Part.makeCylinder(r_out, z_hi - z_lo, base).cut(Part.makeCylinder(r_in, z_hi - z_lo, base))
        turned = model.cut(tube)
        # where the model is smaller than Min Diameter the op leaves it at Min
        # Diameter (as a milling op leaves a floor at its final depth): one
        # diameter across the range, within the model's own length (nothing
        # is built in front of or behind it)
        f_lo, f_hi = max(z_lo, model.BoundBox.ZMin), min(z_hi, model.BoundBox.ZMax)
        if f_hi - f_lo > 1e-6:
            turned = turned.fuse(Part.makeCylinder(r_in, f_hi - f_lo, FreeCAD.Vector(0, 0, f_lo))).removeSplitter()
        if turned.isNull() or not turned.Solids:
            return model
        return turned

    def get_part_outline(self, model=None):
        '''
        Get Part Outline
        '''
        # TODO: Revisit the edge extraction and find a more elegant method
        model = self.model[0].Shape if model is None else model
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

    def warn_if_nothing_cut(self, obj):
        '''
        An operation with nothing to cut makes an empty path, which looks like
        a failure. Say so, and why when Max Diameter is below the part (it is
        where the material starts, not the diameter to turn to).
        '''
        if any(c.Name in ("G1", "G2", "G3", "G33", "G76") for c in self.commandlist):
            return
        message = translate('PathTurn', "{}: no path: nothing of the part to cut in the Z range and between the diameters").format(obj.Label)
        part_dia = 2 * max((-seg.start.X for seg in getattr(self, "part_outline", None) or []), default=0.0)
        max_dia = getattr(obj, "MaxDiameter", None)
        if max_dia is not None and max_dia.Value > 0 and part_dia > max_dia.Value + 1e-6:
            message += translate('PathTurn',
                ". Max Diameter ({:.3f}) is below the part ({:.3f}): it is where the material starts (a surface already "
                "turned smaller). To turn to a diameter, tick Min Diameter and set it; to take a fixed amount off, use "
                "a negative Stock to leave X").format(max_dia.Value, part_dia)
        FreeCAD.Console.PrintWarning(message + "\n")

    def generate_gcode(self, obj):
        '''
        Base function to generate gcode for the OP by writing path command to self.commandlist
        Calls operations op_generate_gcode.
        '''
        opTool = obj.ToolController.Tool

        # the operation and the tool must agree on the kind of insert
        if self.uses_threading_tool:
            if not is_threading_tool(opTool):
                raise RuntimeError(translate('PathTurn', "This operation needs a threading insert (Threading shape)"))
            self.op_generate_gcode(obj, opTool)
            return
        if is_threading_tool(opTool):
            raise RuntimeError(translate('PathTurn', "A threading insert is only for Turn Thread"))
        if self.uses_grooving_tool:
            if not is_grooving_tool(opTool):
                raise RuntimeError(translate('PathTurn',
                    "This operation needs a grooving, parting or full radius insert (Grooving or Full Radius shape)"))
            self.op_generate_gcode(obj, opTool)
            return
        if is_grooving_tool(opTool):
            raise RuntimeError(translate('PathTurn',
                "This operation needs a turning insert (ISO Turning Insert shape); "
                "use Turn Groove for grooving and parting inserts"))

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
