# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Groove: grooving, parting-off style plunging and both-direction
finishing with a grooving or parting insert (Grooving shape). The path comes from liblathe's GrooveOP, which drop-cuts the blade's
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

    turns_to_min_diameter = True

    uses_grooving_tool = True
    uses_pecking = True

    STRATEGIES = ("Plunge", "Side-turn")
    # the default roughing strategy (Turn Groove-Turn: Side-turn)
    default_strategy = "Plunge"

    def opFeatures(self, obj):
        '''Turning features plus base geometry: the selection sets the Z range.'''
        PathOp = PathTurnBase.PathOp
        return (super().opFeatures(obj)
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges | PathOp.FeatureBaseModels)

    def initOperation(self, obj):
        super().initOperation(obj)
        self.add_groove_properties(obj)
        self.add_strategy_properties(obj)

    def add_strategy_properties(self, obj):
        if not hasattr(obj, "Strategy"):
            obj.addProperty("App::PropertyEnumeration", "Strategy", "Turn Path", translate(
                "TurnPath", "Plunge: full-depth plunges side by side. Side-turn: a plunge of one step down, then a "
                            "pass along Z at that depth, alternating direction, level by level: less tool pressure "
                            "in wide grooves"))
            obj.Strategy = list(self.STRATEGIES)
            obj.Strategy = self.default_strategy
        tip = ("Side-turn: depth of each level. Unticked: 90% of the insert's turning depth (half its width without "
               "one), shown greyed")
        if not hasattr(obj, "StepDown"):
            obj.addProperty("App::PropertyLength", "StepDown", "Turn Path", translate("TurnPath", tip))
        if not hasattr(obj, "SetStepDown"):
            obj.addProperty("App::PropertyBool", "SetStepDown", "Turn Path", translate("TurnPath", tip))
        obj.setEditorMode("StepDown", 0 if getattr(obj, "SetStepDown", False) else 1)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        self.add_strategy_properties(obj)
        if not hasattr(obj, "FinishAllowance"):
            self.add_groove_properties(obj)
        for prop, typ, group, tip in (
                ("SpringPass", "App::PropertyBool", "Turn Path", "Repeat the last finish pass once more, with no step over"),
                ("OpToolWidth", "App::PropertyLength", "Op Values", "Width of the operation's insert, for expressions such as Step Over's"),
                ("FinishStepOver", "App::PropertyLength", "Turn Path", "Spacing of the finish passes; 0 splits the finish allowance equally")):
            if not hasattr(obj, prop):
                obj.addProperty(typ, prop, group, translate("TurnPath", tip))
        obj.setEditorMode("OpToolWidth", 1)
        if not hasattr(obj, "FinishDirection"):
            self.add_direction_property(obj)

    FINISH_DIRECTIONS = ("In, across and out", "From each wall to the middle")

    def add_direction_property(self, obj):
        obj.addProperty("App::PropertyEnumeration", "FinishDirection", "Turn Path",
                        translate("TurnPath", "In, across and out: down one wall, along the bottom and up the other "
                                              "(best finish). From each wall to the middle: down each wall and along "
                                              "the bottom toward the middle"))
        obj.FinishDirection = list(self.FINISH_DIRECTIONS)

    def add_groove_properties(self, obj):
        obj.addProperty("App::PropertyLength", "FinishAllowance", "Turn Path",
                        translate("TurnPath", "Material the roughing plunges leave for the finish passes (per side)"))
        obj.addProperty("App::PropertyBool", "SpringPass", "Turn Path",
                        translate("TurnPath", "Repeat the last finish pass once more, with no step over"))
        obj.addProperty("App::PropertyLength", "FinishStepOver", "Turn Path",
                        translate("TurnPath", "Spacing of the finish passes; 0 splits the finish allowance equally"))
        obj.FinishStepOver = FreeCAD.Units.Quantity(0.1, FreeCAD.Units.Length)
        self.add_direction_property(obj)
        obj.addProperty("App::PropertyLength", "OpToolWidth", "Op Values",
                        translate("TurnPath", "Width of the operation's insert, for expressions such as Step Over's"))
        obj.setEditorMode("OpToolWidth", 1)  # read-only
        # a Quantity, not a bare float: the Job dialog's setup-sheet page shows
        # op defaults from a prototype that keeps the raw value
        obj.FinishAllowance = FreeCAD.Units.Quantity(0.2, FreeCAD.Units.Length)

    def op_generate_gcode(self, obj, tool):
        '''Generate the path with liblathe's GrooveOP from the grooving insert's parameters.'''
        op = LLG.GrooveOP()
        op.set_params(self.getProps(obj))
        def length(name, default=0.0):
            return getattr(tool, name).Value if hasattr(tool, name) else default

        width = tool.Width.Value
        if abs(obj.OpToolWidth.Value - width) > 1e-9:
            obj.OpToolWidth = width
        # Step Over defaults to an expression of the insert width (see
        # opSetDefaultValues). Expressions are evaluated before execute, so
        # evaluate it here with the width just set, in case the tool changed.
        step = obj.StepOver.Value
        for prop, expr in obj.ExpressionEngine:
            if prop == "StepOver":
                try:
                    value = obj.evalExpression(expr)
                    step = value.Value if hasattr(value, "Value") else float(value)
                except Exception:
                    pass
        # a Full Radius insert has no CornerRadius: its end is half the width.
        # GroovingDepth was called CuttingDepth in earlier versions of the shape.
        op.set_params({
            'step_over': step,
            'spring_pass': obj.SpringPass,
            'finish_two_sided': obj.FinishDirection == self.FINISH_DIRECTIONS[1],
            'groove_width': width,
            'corner_radius': length("CornerRadius", width / 2),
            'cutting_depth': length("GroovingDepth", length("CuttingDepth")),
            'turning_depth': length("TurningDepth"),
            'finish_allowance': obj.FinishAllowance.Value,
        })
        # roughing strategy and pecking
        turning = length("TurningDepth")
        auto_step = 0.9 * turning if turning > 0 else 0.5 * width
        step_down = obj.StepDown.Value if getattr(obj, "SetStepDown", False) else auto_step
        if not getattr(obj, "SetStepDown", False) and abs(obj.StepDown.Value - auto_step) > 1e-9:
            obj.StepDown = FreeCAD.Units.Quantity(auto_step, FreeCAD.Units.Length)
        op.set_params(dict({'strategy': "side_turn" if getattr(obj, "Strategy", "Plunge") == "Side-turn" else "plunge",
                            'step_down': step_down}, **self.peck_params(obj)))
        op.add_stock(PathTurnHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox))
        op.add_part_edges(self.part_outline)

        for command in op.get_gcode():
            self.commandlist.append(Path.Command(command.get_movement(), command.get_params()))
        for warning in getattr(op, "warnings", []):
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))

    # plunge spacing for multiple grooving as a fraction of the insert width;
    # Sandvik recommends 0.5-0.8 x the insert width for the cuts after the first
    STEP_OVER_FACTOR = 0.7

    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = job.Stock.Shape.BoundBox.ZMin
        obj.FinishPasses = 1
        tc = getattr(obj, "ToolController", None)
        if tc is not None and hasattr(tc.Tool, "Width"):
            obj.OpToolWidth = tc.Tool.Width
        # Step Over follows the insert width; clear the expression to set it by hand
        obj.setExpression("StepOver", "OpToolWidth * {}".format(self.STEP_OVER_FACTOR))

    def opUpdateDepths(self, obj):
        # the selected geometry sets the Z range, otherwise the whole stock
        self.update_depths_from_base(obj)


def SetupProperties():
    return ["FinishPasses", "FinishAllowance", "FinishStepOver", "StockToLeaveX", "StockToLeaveZ", "SpringPass"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnGroove operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnGroove(obj, name, parentJob)
    return obj
