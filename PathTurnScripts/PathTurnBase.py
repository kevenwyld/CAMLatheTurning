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

import PathTurnScripts.PathTurnAddonHelpers as PathTurnAddonHelpers  # puts liblathe on sys.path
from liblathe.base.point import Point
from liblathe.base.segment import Segment
from liblathe.base.boundbox import BoundBox
import PathTurnScripts.TurnFeedsSpeeds as TurnFeedsSpeeds
import PathTurnScripts.TurnSpindleAxis as TurnSpindleAxis
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


def is_drill_tool(tool):
    '''True for a drill (CAM's Drill shape: a Diameter and a TipAngle, none
    of the inserts' parameters).'''
    return (hasattr(tool, "Diameter") and hasattr(tool, "TipAngle")
            and not any(hasattr(tool, p) for p in ("EdgeLength", "ProfileAngle", "Width", "Rotation")))


def is_grooving_tool(tool):
    '''True for a grooving, parting or full radius insert (Grooving / Full Radius shapes).'''
    return (hasattr(tool, "Width") and not hasattr(tool, "TipAngle")
            and any(hasattr(tool, p) for p in ("GroovingDepth", "CuttingDepth", "CornerRadius")))


SIDES = ["External", "Internal"]

# how far off the spindle axis a model (or a circle on it) may be and still be
# taken as round about it: a part placed with CAM's Set Origin can be a few
# microns off (Set Origin uses the face's loose bounding box)
AXIS_TOLERANCE = 0.01

# Min / Max Diameter are worked out unless set by hand: (switch, value, tooltip)
DIAMETER_SWITCHES = (
    ("SetMinDiameter", "MinDiameter",
     "Set Min Diameter by hand: Rough, Profile and Turn Groove turn to it; Face and Partoff stop at it. "
     "Unticked: no inner limit, the op follows the part"),
    ("SetMaxDiameter", "MaxDiameter",
     "Set Max Diameter by hand: the diameter the material starts at. Unticked: the stock's diameter"),
)

# the lift-off between passes and the radial clearance: worked out unless set
CLEARANCE_SWITCHES = (
    ("SetRetract", "Retract",
     "Radial lift-off at the end of each pass. Unticked: step over x finish passes, or 0.5 mm when boring"),
    ("SetRadialClearance", "RadialClearance",
     "Radial distance of the safe position from the stock, or from the hole when boring. "
     "Unticked: the Setup Sheet's safe height offset, or 0.5 mm when boring"),
)
BORING_CLEARANCE = 0.5      # mm, and at most a quarter of the hole's radius

STOCK_X_TIP = ("Material to leave radially, per side. Negative cuts under the model's size "
               "(-0.075 turns a 12 mm model to 11.85)")
STOCK_Z_TIP = "Material to leave axially, on faces and shoulders. Negative cuts under the model's size"


class ObjectOp(PathOp.ObjectOp):

    # operations that work with a grooving insert instead of a turning insert
    uses_grooving_tool = False
    # operations that work with a threading insert
    uses_threading_tool = False
    # operations that work with a drill (Turn Drill)
    uses_drill_tool = False
    # operations for which a Min Diameter set by hand is a diameter to turn
    # to across the Z range (into the model where it is bigger); for the
    # others (Face, Partoff, Thread) it stays their inner limit (e.g. a bore)
    turns_to_min_diameter = False
    # operations that can also cut inside (boring): Side = Internal
    supports_internal = False
    # operations made of passes that lift off at their end (Retract)
    uses_pass_retract = False
    # operations whose passes lead in along Z (Lead-in)
    uses_pass_lead_in = False
    # the op type CAM's feeds & speeds presets know the operation by (see
    # TurnFeedsSpeeds); None: no constant surface speed (Thread, Drill)
    css_op_type = None

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
        self.add_side_property(obj)
        self.add_clearance_properties(obj)
        self.add_lead_in_property(obj)
        self.add_peck_properties(obj)
        self.add_break_edges_properties(obj)
        self.add_css_properties(obj)
        self.add_check_properties(obj)
        obj.addProperty("App::PropertyBool", "AllowGrooving", "Turn Path",
                        translate("TurnPath", "Follow the part into grooves and undercuts as far as the insert's "
                                              "cutting angle allows"))

        obj.StepOver = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length)
        obj.FinishPasses = 2
        # the worked-out clearances, shown before the first recompute
        try:
            obj.Retract = FreeCAD.Units.Quantity(obj.StepOver.Value * obj.FinishPasses, FreeCAD.Units.Length)
            job = PathUtils.findParentJob(obj)
            offset = job.SetupSheet.SafeHeightOffset.Value if job is not None else 3.0
            obj.RadialClearance = FreeCAD.Units.Quantity(offset, FreeCAD.Units.Length)
        except Exception:
            pass

    def add_clearance_properties(self, obj):
        '''Retract and Radial clearance, each with its Set switch.'''
        for switch, prop, tip in CLEARANCE_SWITCHES:
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyLength", prop, "Turn Path", translate("TurnPath", tip))
            if not hasattr(obj, switch):
                obj.addProperty("App::PropertyBool", switch, "Turn Path", translate("TurnPath", tip))
            # (getattr with a default: the Job dialog's operation prototypes
            # cannot read back a property just added)
            obj.setEditorMode(prop, 0 if getattr(obj, switch, False) else 1)

    def add_lead_in_property(self, obj):
        '''Lead-in, with its Set switch, for the operations whose passes lead
        in along Z (Turn Thread has its own, along the thread).'''
        if not self.uses_pass_lead_in:
            return
        tip = ("How far in front of the Z range the passes start along Z; 0 enters them radially. "
               "Unticked: worked out from the stock and part in front of the range")
        if not hasattr(obj, "LeadIn"):
            obj.addProperty("App::PropertyLength", "LeadIn", "Turn Path", translate("TurnPath", tip))
        if not hasattr(obj, "SetLeadIn"):
            obj.addProperty("App::PropertyBool", "SetLeadIn", "Turn Path", translate("TurnPath", tip))
        obj.setEditorMode("LeadIn", 0 if getattr(obj, "SetLeadIn", False) else 1)

    def show_lead_in(self, obj, op):
        '''The lead-in liblathe worked out, in the (greyed) field.'''
        used = getattr(op, "lead_in_used", None)
        if used is not None and hasattr(obj, "LeadIn") and not getattr(obj, "SetLeadIn", False) \
                and abs(obj.LeadIn.Value - used) > 1e-9:
            obj.LeadIn = FreeCAD.Units.Quantity(used, FreeCAD.Units.Length)

    def clearance_values(self, obj):
        '''(retract, radial clearance) the op uses: as set, or worked out.'''
        if getattr(self, "mirror_r", None) is not None:
            auto = min(BORING_CLEARANCE, 0.25 * self.hole_r)
            auto_retract, auto_clearance = auto, auto
        else:
            auto_retract = obj.StepOver.Value * obj.FinishPasses
            auto_clearance = PathUtils.findParentJob(obj).SetupSheet.SafeHeightOffset.Value
        retract = obj.Retract.Value if getattr(obj, "SetRetract", False) else auto_retract
        clearance = obj.RadialClearance.Value if getattr(obj, "SetRadialClearance", False) else auto_clearance
        return retract, clearance

    def show_clearance_values(self, obj):
        '''The worked-out values in the (greyed) fields.'''
        retract, clearance = self.clearance_values(obj)
        for switch, prop, value in (("SetRetract", "Retract", retract), ("SetRadialClearance", "RadialClearance", clearance)):
            if hasattr(obj, prop) and not getattr(obj, switch) and abs(getattr(obj, prop).Value - value) > 1e-9:
                setattr(obj, prop, FreeCAD.Units.Quantity(value, FreeCAD.Units.Length))

    # pecking on plunges (Turn Groove, Turn Groove-Turn, Turn Partoff)
    uses_pecking = False
    # edge breaking: chamfering every sharp outside corner the finish goes
    # over (Turn Rough's cleanup pass, Turn Profile, Turn Face)
    uses_break_edges = False

    def auto_min_diameter(self, obj):
        '''Min Diameter when not set by hand: none (0), the op follows the part
        (Turn Face: the selected face's inner edge, when the part is there).'''
        return 0.0

    def add_break_edges_properties(self, obj):
        if not self.uses_break_edges:
            return
        tip = ("Chamfer every sharp outside corner the finishing pass goes over by this much. "
               "Inside corners and modelled chamfers or fillets are left alone")
        if not hasattr(obj, "BreakEdges"):
            obj.addProperty("App::PropertyBool", "BreakEdges", "Turn Path", translate("TurnPath", tip))
        if not hasattr(obj, "BreakEdgeSize"):
            obj.addProperty("App::PropertyLength", "BreakEdgeSize", "Turn Path", translate("TurnPath", tip))
            obj.BreakEdgeSize = FreeCAD.Units.Quantity(0.2, FreeCAD.Units.Length)

    def add_check_properties(self, obj):
        '''The checks waived for this operation (its refusals become warnings:
        see liblathe.base.refusal), and the last refusal, for the panel.'''
        if not hasattr(obj, "IgnoredChecks"):
            obj.addProperty("App::PropertyStringList", "IgnoredChecks", "Turn Path", translate("TurnPath",
                "Checks waived for this operation: it warns and generates the path instead of refusing. "
                "Set with Generate anyway on the operation's page, or edit the names here"))
        if not hasattr(obj, "LastRefusal"):
            obj.addProperty("App::PropertyStringList", "LastRefusal", "Turn Path", translate("TurnPath",
                "The check that refused the path at the last recompute, and why"))
        obj.setEditorMode("LastRefusal", 2)

    # the addon's own waivable checks, beside liblathe's (liblathe.base.refusal.CHECKS):
    # name -> what the operation does when it is waived
    CHECKS = {"css-no-max-rpm": "posts G96 without D, so the machine's own limit applies"}

    def refuse(self, obj, check, message):
        '''The addon's own waivable refusals, as liblathe's: raise a Refusal
        naming the check, unless it is waived: then warn and return.'''
        from liblathe.base.refusal import Refusal
        if check not in (getattr(obj, "IgnoredChecks", None) or []):
            raise Refusal(check, message)
        FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, translate("TurnPath",
            "Generated anyway (check {} waived): {}").format(check, message)))

    CSS_PROPERTIES = (
        ("App::PropertyBool", "ConstantSurfaceSpeed",
         "Constant surface speed (G96): the spindle speed follows the cutting diameter, up to Max spindle speed. "
         "G97 restores the tool controller's rpm at the end"),
        ("App::PropertyFloat", "SurfaceSpeed",
         "Surface speed, m/min. Unticked: the tool's Feeds & Speeds preset for the stock material, "
         "else the material's speed for HSS or Carbide"),
        ("App::PropertyBool", "SetSurfaceSpeed", "Set the surface speed by hand"),
        ("App::PropertyString", "SurfaceSpeedSource", "Where the surface speed comes from"),
        ("App::PropertyFloat", "MaxSpindleSpeed",
         "Maximum spindle speed under constant surface speed, rpm. Unticked: the Job's machine's spindle maximum"),
        ("App::PropertyBool", "SetMaxSpindleSpeed", "Set the maximum spindle speed by hand"),
    )

    def add_css_properties(self, obj):
        '''Constant surface speed, for the operations that cut with a turning
        or grooving insert.'''
        if self.css_op_type is None:
            return
        for kind, name, tip in self.CSS_PROPERTIES:
            if not hasattr(obj, name):
                obj.addProperty(kind, name, "Spindle", translate("TurnPath", tip))
        obj.setEditorMode("SurfaceSpeedSource", 1)
        self.show_css_modes(obj)

    @staticmethod
    def show_css_modes(obj):
        for switch, prop in (("SetSurfaceSpeed", "SurfaceSpeed"), ("SetMaxSpindleSpeed", "MaxSpindleSpeed")):
            if hasattr(obj, prop):
                obj.setEditorMode(prop, 0 if getattr(obj, switch, False) else 1)

    def apply_css(self, obj):
        '''Work out the surface speed and maximum spindle speed (shown even
        with constant surface speed off), and with it on, wrap the path in G96
        ... G97.'''
        if self.css_op_type is None or not hasattr(obj, "ConstantSurfaceSpeed"):
            return
        job = PathUtils.findParentJob(obj)
        tc = obj.ToolController
        why = ""
        if obj.SetSurfaceSpeed:
            source = translate("TurnPath", "set by hand")
        else:
            vc, source = TurnFeedsSpeeds.surface_speed(tc.Tool, job, self.css_op_type)
            if vc is None:
                why, source, vc = source, translate("TurnPath", "none found"), 0.0
            if abs(obj.SurfaceSpeed - vc) > 1e-9:
                obj.SurfaceSpeed = vc
        if obj.SurfaceSpeedSource != source:
            obj.SurfaceSpeedSource = source
        machine_max = TurnFeedsSpeeds.machine_max_rpm(job)
        if not obj.SetMaxSpindleSpeed and abs(obj.MaxSpindleSpeed - machine_max) > 1e-9:
            obj.MaxSpindleSpeed = machine_max
        self.show_css_modes(obj)
        if not obj.ConstantSurfaceSpeed:
            return

        if obj.SurfaceSpeed <= 0:
            raise RuntimeError(translate("TurnPath",
                "Constant surface speed needs a surface speed: {}. Add a Feeds & Speeds preset to the tool, "
                "give the Job's stock a material, or set Surface speed").format(
                    why or translate("TurnPath", "it is set to 0")))
        if obj.MaxSpindleSpeed <= 0:
            self.refuse(obj, "css-no-max-rpm", translate("TurnPath",
                "Constant surface speed needs a maximum spindle speed. Set the spindle's maximum rpm in the Job's "
                "machine, or set Max spindle speed"))
        rpm = float(tc.SpindleSpeed or 0.0)
        if rpm <= 0:
            raise RuntimeError(translate("TurnPath",
                "Constant surface speed needs the tool controller's spindle speed (G97 returns to it)"))
        if obj.SetMaxSpindleSpeed and 0 < machine_max < obj.MaxSpindleSpeed:
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, translate("TurnPath",
                "Max spindle speed ({:.0f} rpm) is above the machine's ({:.0f} rpm)").format(
                    obj.MaxSpindleSpeed, machine_max)))
        # after the operation's own comments, as CAM puts coolant on before the first move
        first = 0
        while first < len(self.commandlist) and self.commandlist[first].Name.startswith("("):
            first += 1
        g96 = {"S": obj.SurfaceSpeed}
        if obj.MaxSpindleSpeed > 0:          # waived without one: G96 without D, the machine's own limit
            g96["D"] = obj.MaxSpindleSpeed
        self.commandlist.insert(first, Path.Command("G96", g96))
        self.commandlist.append(Path.Command("G97", {"S": rpm}))

    def report_broken_edges(self, obj, op):
        broken = getattr(op, "edges_broken", [])
        if broken:
            FreeCAD.Console.PrintMessage("{}: edges broken ({} chamfer) at {}\n".format(
                obj.Label, FreeCAD.Units.Quantity(obj.BreakEdgeSize.Value, FreeCAD.Units.Length).UserString,
                ", ".join("radius {:.3f}, Z {:.3f}".format(-p.X, p.Z) for p in broken)))

    def add_peck_properties(self, obj):
        if not self.uses_pecking:
            return
        for prop, typ, tip, default in (
                ("Peck", "App::PropertyBool", "Plunge in pecks, backing off between them to break the chip", False),
                ("PeckDepth", "App::PropertyLength", "How far each peck feeds in", 2.0),
                ("PeckRetract", "App::PropertyLength", "How far the tool backs off between pecks", 0.2),
                ("PeckFullRetract", "App::PropertyBool",
                 "Retract out of the cut between pecks, not just back off", False)):
            if not hasattr(obj, prop):
                obj.addProperty(typ, prop, "Pecking", translate("TurnPath", tip))
                setattr(obj, prop, FreeCAD.Units.Quantity(default, FreeCAD.Units.Length) if typ.endswith("Length") else default)

    def peck_params(self, obj):
        if not getattr(obj, "Peck", False):
            return {'peck_depth': 0.0}
        return {'peck_depth': obj.PeckDepth.Value, 'peck_retract': obj.PeckRetract.Value,
                'peck_full_retract': bool(obj.PeckFullRetract)}

    def add_side_property(self, obj):
        '''Side (External / Internal) for the operations that can bore.'''
        if self.supports_internal and not hasattr(obj, "Side"):
            obj.addProperty("App::PropertyEnumeration", "Side", "Turn Path", translate(
                "TurnPath", "External turns the outside. Internal bores from the hole set as Min Diameter "
                            "out to the model, with a boring tool"))
            obj.Side = SIDES

    def is_internal(self, obj):
        return self.supports_internal and getattr(obj, "Side", SIDES[0]) == SIDES[1]

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

    def onDocumentRestored(self, obj):
        # CAM's restore reads Base's type first and fails without one: add it
        # for ops saved before they selected geometry
        if PathOp.FeatureBaseGeometry & self.opFeatures(obj) and not hasattr(obj, "Base"):
            self.addBaseProperty(obj)
        super().onDocumentRestored(obj)

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
        self.add_side_property(obj)
        self.add_clearance_properties(obj)
        self.add_lead_in_property(obj)
        self.add_peck_properties(obj)
        self.add_break_edges_properties(obj)
        self.add_css_properties(obj)
        self.add_check_properties(obj)
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
        '''Z extent of the selected base geometry as (start depth, final depth), or
        None when nothing is selected.'''
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
        # a refusal from an earlier recompute no longer applies
        if getattr(obj, "LastRefusal", None):
            obj.LastRefusal = []
        # the Job's models and stock must be round about the spindle axis
        TurnSpindleAxis.report_off_axis(obj, PathUtils.findParentJob(obj))
        PathLog.track()
        self.tool = None
        # worked out unless set by hand: Max Diameter the stock's, Min
        # Diameter none (0: the op follows the part); shown in the fields
        if not getattr(obj, "SetMaxDiameter", True):
            stock = self.stock_diameter(obj)
            if stock is not None and abs(obj.MaxDiameter.Value - stock) > 1e-9:
                obj.MaxDiameter = FreeCAD.Units.Quantity(stock, FreeCAD.Units.Length)
        if not getattr(obj, "SetMinDiameter", True):
            auto = self.auto_min_diameter(obj)
            if abs(obj.MinDiameter.Value - auto) > 1e-9:
                obj.MinDiameter = FreeCAD.Units.Quantity(auto, FreeCAD.Units.Length)
        self.minDia = obj.MinDiameter.Value
        self.maxDia = obj.MaxDiameter.Value

        if self.minDia >= self.maxDia:
            raise RuntimeError(translate('PathTurn', "Min Diameter must be below Max Diameter"))

        # bounding boxes are padded by the modelling tolerance (~1e-7 mm), so a
        # flat face selected on the Z Range page gives a tiny positive range
        if obj.StartDepth.Value - obj.FinalDepth.Value <= 1e-4:
            if self.depths_from_base(obj):
                raise RuntimeError(translate('PathTurn',
                    "The selection has no length along Z. Select geometry at two different Z positions, "
                    "or set Front and Back by hand"))
            raise RuntimeError(translate('PathTurn', "Front (Z) must be above Back (Z)"))

        self.startOffset = 0
        self.endOffset = 0
        self.allowGrooving = obj.AllowGrooving
        self.stepOver = obj.StepOver.Value
        self.finishPasses = obj.FinishPasses
        self.stockToLeaveX = obj.StockToLeaveX.Value
        self.stockToLeaveZ = obj.StockToLeaveZ.Value

        # Clear any existing gcode
        obj.Path.Commands = []

        self.stock_silhoutte = self.get_stock_silhoutte(obj)
        if self.is_internal(obj):
            self.setup_internal(obj)
        else:
            self.mirror_r = None
            self.part_outline = self.get_part_outline(self.turned_model(obj))
        self.show_clearance_values(obj)
        from liblathe.base.refusal import Refusal
        try:
            self.generate_gcode(obj)
            self.warn_if_nothing_cut(obj)
            self.apply_css(obj)
        except Refusal as refusal:
            # for the panel's Generate anyway (and kept with the document)
            if hasattr(obj, "LastRefusal") and list(obj.LastRefusal) != [refusal.check, str(refusal)]:
                obj.LastRefusal = [refusal.check, str(refusal)]
            raise

    def getProps(self, obj):
        parentJob = PathUtils.findParentJob(obj)

        props = {}
        props['min_dia'] = self.minDia
        props['ignored_checks'] = tuple(getattr(obj, "IgnoredChecks", None) or ())
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
        if getattr(self, "mirror_r", None) is not None:
            # boring, in the mirrored space (see setup_internal): the stock's top
            # is the hole and the inner limit the max diameter
            R = self.mirror_r
            props['extra_dia'] = 0.0
            props['min_dia'] = 2 * max(0.0, R - self.maxDia / 2)
            # and nothing past the hole: no facing to the axis or following
            # it beyond a blind bore's bottom
            props['clip_outer'] = True
        if hasattr(obj, "Retract"):
            retract, clearance = self.clearance_values(obj)
            props['clearance_x'] = clearance
            # unset outside: liblathe's own (the same value), so paths stay as they were
            props['retract'] = retract if (getattr(obj, "SetRetract", False) or getattr(self, "mirror_r", None) is not None) else None
        if self.uses_pass_lead_in and getattr(obj, "SetLeadIn", False):
            props['pass_lead_in'] = obj.LeadIn.Value
        if self.uses_break_edges and getattr(obj, "BreakEdges", False):
            props['break_edges'] = obj.BreakEdgeSize.Value
        return props

    def get_stock_silhoutte(self, obj):
        '''A plane over the whole stock's XZ section. Also sets startOffset / endOffset,
        the op's Z limits as offsets from the stock ends (negative: inside the stock).'''
        stockBB = self.stock.Shape.BoundBox
        stock_z_pos = stockBB.ZMax

        self.startOffset = obj.StartDepth.Value - stockBB.ZMax
        self.endOffset = stockBB.ZMin - obj.FinalDepth.Value

        stock_plane_length = stockBB.ZLength
        stock_plane_width = stockBB.XLength / 2
        stock_plane = Part.makePlane(stock_plane_length, stock_plane_width,
                                     FreeCAD.Vector(-stock_plane_width, 0, stock_z_pos), FreeCAD.Vector(0, -1, 0))
        return stock_plane

    def setup_internal(self, obj):
        '''Boring as external turning in a mirror: radius r maps to R - r (R the stock
        radius), so the bore becomes an outer profile; lathe_commands() maps the output back.'''
        if not getattr(obj, "SetMinDiameter", False) or obj.MinDiameter.Value <= 0:
            raise RuntimeError(translate('PathTurn',
                "Internal: tick Min Diameter and set it to the hole to bore from (the drill size)"))
        model = self.job_model_shape(obj)
        mb = model.BoundBox
        R = max(self.stock.Shape.BoundBox.XLength / 2, mb.XMax, -mb.XMin, mb.YMax, -mb.YMin)
        self.hole_r = obj.MinDiameter.Value / 2
        if self.hole_r >= R:
            raise RuntimeError(translate('PathTurn', "Internal: the hole (Min Diameter) is not inside the stock"))
        V = FreeCAD.Vector
        z0, z1 = mb.ZMin, mb.ZMax
        rect = Part.Face(Part.makePolygon([V(0, 0, z0), V(R, 0, z0), V(R, 0, z1), V(0, 0, z1), V(0, 0, z0)]))
        voids = [f for f in rect.cut(model).Faces if f.BoundBox.XMin < 1e-6]
        if not voids:
            raise RuntimeError(translate('PathTurn', "Internal: the model has no bore open to the axis"))
        void = voids[0] if len(voids) == 1 else voids[0].fuse(voids[1:])
        # the op works from the hole out to the bore's surface: unless Max
        # Diameter is set, it is the bore's largest diameter (shown in the
        # field), so nothing beyond the bore (e.g. the part's front face) is cut
        self.bore_r = void.BoundBox.XMax
        if not getattr(obj, "SetMaxDiameter", False):
            if abs(obj.MaxDiameter.Value - 2 * self.bore_r) > 1e-9:
                obj.MaxDiameter = FreeCAD.Units.Quantity(2 * self.bore_r, FreeCAD.Units.Length)
            self.maxDia = 2 * self.bore_r
        mirrored = void.mirror(V(R / 2, 0, 0), V(1, 0, 0))
        part2d = rect.cut(mirrored)
        solids = [f.revolve(V(0, 0, 0), V(0, 0, 1), 360) for f in part2d.Faces]
        solid = solids[0] if len(solids) == 1 else solids[0].fuse(solids[1:])
        self.mirror_r = R
        self.part_outline = self.get_part_outline(solid)

    def report_lathe_warnings(self, obj, op):
        '''liblathe's warnings for the operation (e.g. the insert's outline
        reaching into the part) in the Report view.'''
        for warning in getattr(op, "warnings", []):
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))

    def lathe_stock_box(self):
        '''The stock for liblathe: the stock's silhouette, or for boring (in
        the mirrored space) the material from the hole outward.'''
        if getattr(self, "mirror_r", None) is not None:
            bb = self.stock.Shape.BoundBox
            return BoundBox(Point(-(self.mirror_r - self.hole_r), 0, bb.ZMin), Point(0, 0, bb.ZMax))
        return PathTurnAddonHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox)

    def lathe_commands(self, commands):
        '''liblathe's commands as path commands; for boring mapped back out of
        the mirror: X to R - X, the arc's radial offset I reversed, G2 / G3
        swapped (a mirror reverses the direction of arcs).'''
        R = getattr(self, "mirror_r", None)
        out = []
        for command in commands:
            name, params = command.get_movement(), dict(command.get_params())
            if R is not None:
                if "X" in params:
                    params["X"] = R - params["X"]
                if "I" in params:
                    params["I"] = -params["I"]
                name = {"G2": "G3", "G3": "G2"}.get(name, name)
            out.append(Path.Command(name, params))
        return out

    def job_model_shape(self, obj):
        '''All the Job's models fused into one shape: on a lathe their union is what is turned.'''
        shapes = [m.Shape for m in self.model if getattr(m, "Shape", None) is not None and not m.Shape.isNull()]
        if not shapes:
            return self.model[0].Shape
        if len(shapes) == 1:
            return shapes[0]
        fused = shapes[0].fuse(shapes[1:])
        try:
            fused = fused.removeSplitter()
        except Exception:
            pass
        return fused

    def turned_model(self, obj):
        '''The model as the op leaves it: with Min Diameter set by hand, the model cut to
        that diameter across the Z range (and filled up to it where smaller).'''
        model = self.job_model_shape(obj)
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
        # fill up to Min Diameter where the model is smaller, within its own length
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
        model = self.job_model_shape(None) if model is None else model
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
                "Turning: %d outline edge(s) not connected to the profile were ignored\n" % unchained)

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
        if any(c.Name in ("G1", "G2", "G3", "G33", "G76", "G73", "G81", "G82", "G83") for c in self.commandlist):
            return
        message = translate('PathTurn', "{}: no path: nothing to cut in the Z range between Min and Max Diameter").format(obj.Label)
        part_dia = 2 * max((-seg.start.X for seg in getattr(self, "part_outline", None) or []), default=0.0)
        max_dia = getattr(obj, "MaxDiameter", None)
        # (not for a part only a little off the axis: its outline's side is up to
        # twice that much bigger)
        if max_dia is not None and max_dia.Value > 0 and part_dia > max_dia.Value + 2 * AXIS_TOLERANCE:
            message += translate('PathTurn',
                ". Max Diameter ({:.3f}) is below the part ({:.3f}); it is where the material starts. "
                "To turn down to a diameter set Min Diameter, or use a negative Stock to leave X").format(max_dia.Value, part_dia)
        FreeCAD.Console.PrintWarning(message + "\n")

    def generate_gcode(self, obj):
        '''
        Base function to generate gcode for the OP by writing path command to self.commandlist
        Calls operations op_generate_gcode.
        '''
        opTool = obj.ToolController.Tool

        # the operation and the tool must agree on the kind of insert
        if self.uses_drill_tool:
            if not is_drill_tool(opTool):
                raise RuntimeError(translate('PathTurn', "This operation needs a drill (CAM's Drill shape)"))
            self.op_generate_gcode(obj, opTool)
            return
        if is_drill_tool(opTool):
            raise RuntimeError(translate('PathTurn', "A drill is only for Turn Drill"))
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
                "This operation needs a turning insert (ISO Turning Insert shape). "
                "Grooving and parting inserts are for Turn Groove and Turn Partoff"))

        # a turning insert has these; anything else (e.g. CAM's default end
        # mill on a new Job) cannot turn, and would fail obscurely later
        missing = [p for p in ("TipAngle", "EdgeLength", "TipRadius", "Rotation") if not hasattr(opTool, p)]
        if missing:
            raise RuntimeError(translate('PathTurn',
                "This operation needs a turning insert (ISO Turning Insert shape). "
                "The tool {} has no {}").format(getattr(opTool, "Label", "?"), ", ".join(missing)))

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
    """Chain edge dicts (p0, p1, mid, angle) into [(start, end, signed_angle)] from the
    front (X=0, max Z) to the back, arc angles in liblathe's sign (positive anticlockwise).
    Also returns the number of edges that could not be chained."""
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
