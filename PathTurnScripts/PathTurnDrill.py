# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Drill: drilling on the spindle axis.

The hole is the selected cylindrical face (Z Range page): its front and back
give the depth, the drill runs on the axis (X 0). The cycle is a canned one
(G81 drill, G82 drill with a dwell, G83 peck with full retract, G73 chip
break), or the same moves written out. Canned cycles drill along the active
plane's axis, so the program switches to G17 for the cycle and back to G18
after it: drilling along Z, on a lathe and on a mill used as a lathe alike.
"""
import math

import FreeCAD
import Path
import PathScripts.PathUtils as PathUtils
import PathTurnScripts.PathTurnBase as PathTurnBase

from PySide import QtCore

__title__ = "Path Turn Drill Operation"
__doc__ = "Drilling on the spindle axis."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


CYCLES = ["Peck (G83)", "Chip break (G73)", "Drill (G81)", "Dwell (G82)"]
CODE = {"Peck (G83)": "G83", "Chip break (G73)": "G73", "Drill (G81)": "G81", "Dwell (G82)": "G82"}
CHIP_BREAK = 0.25           # mm the drill backs off between chip-break pecks (explicit moves)


def _cylinder_type():
    import Part
    return Part.Cylinder


class ObjectTurnDrill(PathTurnBase.ObjectOp):
    '''Proxy class for drilling on the spindle axis.'''

    uses_drill_tool = True

    # Only what drilling uses: the tool, coolant, depths (CAM's machinery) and
    # base geometry (the hole). Not the turning operations' diameters, stock to
    # leave, side, lead-in or clearances, nor their outline work.
    def opFeatures(self, obj):
        PathOp = PathTurnBase.PathOp
        return (PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureCoolant
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges)

    def initOperation(self, obj):
        self.add_drill_properties(obj)

    def opOnDocumentRestored(self, obj):
        PathTurnBase.PathOp.ObjectOp.opOnDocumentRestored(self, obj)
        self.add_drill_properties(obj)
        self.migrate_hole_properties(obj)

    def migrate_hole_properties(self, obj):
        '''Hole start / Hole depth (an earlier version) become the Z range's
        Front / Back, as for the other operations: a value set by hand stays
        set (its expression removed).'''
        if not hasattr(obj, "HoleStart"):
            return
        start = obj.HoleStart.Value
        if getattr(obj, "SetHoleStart", False):
            obj.setExpression("StartDepth", None)
            obj.StartDepth = FreeCAD.Units.Quantity(start, FreeCAD.Units.Length)
        if getattr(obj, "SetHoleDepth", False):
            obj.setExpression("FinalDepth", None)
            obj.FinalDepth = FreeCAD.Units.Quantity(start - obj.HoleDepth.Value, FreeCAD.Units.Length)
        for prop in ("SetHoleStart", "HoleStart", "SetHoleDepth", "HoleDepth"):
            if hasattr(obj, prop):
                obj.removeProperty(prop)

    def opExecute(self, obj):
        tool = obj.ToolController.Tool if obj.ToolController else None
        if tool is None or not PathTurnBase.is_drill_tool(tool):
            raise RuntimeError(translate('PathTurn', "This operation needs a drill (CAM's Drill shape)"))
        self.op_generate_gcode(obj, tool)

    def add_drill_properties(self, obj):
        group = "Drill"

        def add(kind, name, tip):
            if not hasattr(obj, name):
                obj.addProperty(kind, name, group, translate("TurnPath", tip))
                return True
            return False

        if add("App::PropertyEnumeration", "Cycle",
               "Peck (G83): back out of the hole after each peck; Chip break (G73): back off a little; "
               "Drill (G81): straight to depth; Dwell (G82): to depth, then a dwell"):
            obj.Cycle = CYCLES
        if add("App::PropertyLength", "PeckDepth", "Depth of each peck (Peck and Chip break)"):
            obj.PeckDepth = FreeCAD.Units.Quantity(2.0, FreeCAD.Units.Length)
        if add("App::PropertyFloat", "DwellTime", "Seconds at the bottom (Dwell)"):
            obj.DwellTime = 0.5
        if add("App::PropertyLength", "RetractHeight",
               "Distance in front of the hole where each peck starts and the drill retracts to (the R plane)"):
            obj.RetractHeight = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length)
        add("App::PropertyBool", "DepthToTip",
            "Drill to the tip: the drill's point reaches Back (Z). Off (default): its full diameter does, so the "
            "point goes deeper by its length")
        if add("App::PropertyBool", "UseCannedCycle",
               "Write the cycle as a canned cycle (G81/G82/G83/G73, in G17, then back to G18); off: the same "
               "moves written out"):
            obj.UseCannedCycle = True
        if add("App::PropertyString", "DrillReport", "What is drilled and how (read only)"):
            obj.setEditorMode("DrillReport", 1)

    def selected_hole(self, obj):
        '''The selected cylindrical face, or None.'''
        for base, subs in (getattr(obj, "Base", None) or []):
            for sub in subs:
                if sub.startswith("Face"):
                    face = base.Shape.getElement(sub)
                    if isinstance(face.Surface, _cylinder_type()):
                        return face
        return None

    # The Z range is the hole: Front where it starts, Back where the drill's
    # full diameter (or its tip, Depth to tip) ends, as Back is for every
    # operation. Worked out from the selected hole; with nothing selected the
    # hole starts at the part's front and Back is to be set.
    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = obj.OpFinalDepth = self.part_front(obj, job)

    def opUpdateDepths(self, obj):
        selected = self.depths_from_base(obj)
        if selected:
            obj.OpStartDepth, obj.OpFinalDepth = selected
        else:
            obj.OpStartDepth = obj.OpFinalDepth = self.part_front(obj)

    def part_front(self, obj, job=None):
        job = job or PathUtils.findParentJob(obj)
        models = [m for m in (job.Model.Group if job is not None else []) if hasattr(m, "Shape")]
        if models:
            return max(m.Shape.BoundBox.ZMax for m in models)
        return job.Stock.Shape.BoundBox.ZMax if job is not None else 0.0

    def op_generate_gcode(self, obj, tool):
        hole = self.selected_hole(obj)
        if hole is not None:
            axis_offset = math.hypot(hole.Surface.Center.x, hole.Surface.Center.y)
            if axis_offset > 0.01 or abs(abs(hole.Surface.Axis.z) - 1) > 1e-6:
                raise RuntimeError(translate('PathTurn', "The selected hole is not on the spindle axis: Turn Drill drills on the axis"))
        front, back = obj.StartDepth.Value, obj.FinalDepth.Value
        depth = front - back
        if depth <= 1e-6:
            raise RuntimeError(translate('PathTurn',
                "Select the hole to drill (its cylindrical face) on the Z Range page, or tick Back (Z) there and set "
                "where the hole ends"))
        d = tool.Diameter.Value
        tip_angle = tool.TipAngle.Value
        tip = (d / 2) / math.tan(math.radians(tip_angle) / 2) if 0 < tip_angle < 180 else 0.0
        bottom = back if obj.DepthToTip else back - tip
        r_plane = front + obj.RetractHeight.Value
        job = PathUtils.findParentJob(obj)
        clearance = job.SetupSheet.SafeHeightOffset.Value
        stock = self.stock.Shape.BoundBox
        safe_z = max(stock.ZMax, r_plane) + clearance
        safe_x = stock.XLength / 2 + clearance
        # the drilling feed is the vertical feed; with none set the horizontal
        # one (CAM Sanity warns about it)
        feed = obj.ToolController.VertFeed.Value or obj.ToolController.HorizFeed.Value
        code = CODE[obj.Cycle]
        peck = max(obj.PeckDepth.Value, 0.01)

        hole_d = 2 * hole.Surface.Radius if hole is not None else d
        notes = []
        if abs(hole_d - d) > 0.05:
            notes.append("the drill ({:.3f}) is not the hole's size ({:.3f})".format(d, hole_d))
            FreeCAD.Console.PrintWarning("{}: the drill ({:.3f}) is not the hole's size ({:.3f})\n".format(obj.Label, d, hole_d))

        cmds = [Path.Command("G18"),
                Path.Command("G0", {"X": safe_x}), Path.Command("G0", {"X": safe_x, "Z": safe_z}),
                Path.Command("G0", {"X": 0.0, "Z": safe_z}), Path.Command("G0", {"X": 0.0, "Z": r_plane})]
        if obj.UseCannedCycle:
            params = {"X": 0.0, "Y": 0.0, "Z": bottom, "R": r_plane, "F": feed}
            if code in ("G83", "G73"):
                params["Q"] = peck
            if code == "G82":
                params["P"] = obj.DwellTime
            cmds += [Path.Command("G17"), Path.Command("G98"), Path.Command(code, params),
                     Path.Command("G80"), Path.Command("G18")]
        else:
            cmds += self.explicit_moves(code, front, bottom, r_plane, peck, feed, obj.DwellTime)
        # out of the hole along Z, then away from the axis
        cmds += [Path.Command("G0", {"X": 0.0, "Z": safe_z}), Path.Command("G0", {"X": safe_x, "Z": safe_z})]
        self.commandlist.extend(cmds)

        report = ["Drill \u00d8{:.3f}, point {:.0f}\u00b0 ({:.3f} long)".format(d, tip_angle, tip),
                  "{}{}: from Z {:.3f} (R plane) to Z {:.3f}".format(
                      obj.Cycle, ", pecks {:.3f}".format(peck) if code in ("G83", "G73") else "", r_plane, bottom),
                  "{} reaches Back, Z {:.3f}: {:.3f} deep from Front, Z {:.3f}".format(
                      "The tip" if obj.DepthToTip else "The full diameter", back, depth, front)]
        report += ["Note: " + n for n in notes]
        text = "\n".join(report)
        if obj.DrillReport != text:
            obj.DrillReport = text


    @staticmethod
    def explicit_moves(code, front, bottom, r_plane, peck, feed, dwell):
        '''The cycle written out, from the R plane (the drill is there):
        G83 pecks, backing out to the R plane after each and returning at
        rapid to just short of where it reached; G73 pecks, backing off a
        little to break the chip; G81 straight to depth; G82 the same, then a
        dwell. Back to the R plane at the end.'''
        out = []
        if code in ("G83", "G73"):
            reached = front                   # the hole starts here
            while True:
                target = max(bottom, reached - peck)
                out.append(Path.Command("G1", {"X": 0.0, "Z": target, "F": feed}))
                reached = target
                if target <= bottom + 1e-9:
                    break
                if code == "G83":
                    out.append(Path.Command("G0", {"X": 0.0, "Z": r_plane}))
                    out.append(Path.Command("G0", {"X": 0.0, "Z": min(r_plane, reached + 0.5)}))
                else:
                    out.append(Path.Command("G0", {"X": 0.0, "Z": reached + CHIP_BREAK}))
        else:
            out.append(Path.Command("G1", {"X": 0.0, "Z": bottom, "F": feed}))
            if code == "G82":
                out.append(Path.Command("G4", {"P": dwell}))
        out.append(Path.Command("G0", {"X": 0.0, "Z": r_plane}))
        return out


def SetupProperties():
    return ["Cycle", "PeckDepth", "DwellTime", "RetractHeight", "DepthToTip", "UseCannedCycle"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a Turn Drill operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnDrill(obj, name, parentJob)
    return obj
