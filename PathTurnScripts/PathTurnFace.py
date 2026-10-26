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
import PathScripts.PathUtils as PathUtils
import PathTurnScripts.PathTurnBase as PathTurnBase
import PathTurnScripts.TurnFeedsSpeeds as TurnFeedsSpeeds
from PySide import QtCore

import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers

import liblathe.op.face as LLF

__title__ = "Path Turn Facing Operation"
__author__ = "dubstar-04 (Daniel Wood)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Class implementation for turning facing operations."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTurnFace(PathTurnBase.ObjectOp):
    '''Proxy class for turning facing operations.'''
    # CAM's feeds & speeds op type (constant surface speed)
    css_op_type = TurnFeedsSpeeds.OP_TYPE_ROUGHING

    uses_pass_retract = True
    uses_break_edges = True

    def opFeatures(self, obj):
        '''Turning features plus base faces: a selected face (flat, square to
        the axis) is the plane to face down to.'''
        return super().opFeatures(obj) | PathTurnBase.PathOp.FeatureBaseFaces

    def selected_face(self, obj):
        '''The selected flat face square to the spindle axis, or None.'''
        import Part
        for base, subs in (getattr(obj, "Base", None) or []):
            for sub in subs:
                if sub.startswith("Face"):
                    face = base.Shape.getElement(sub)
                    if isinstance(face.Surface, Part.Plane) and abs(abs(face.Surface.Axis.z) - 1) < 1e-6:
                        return base, face
        return None

    def part_front(self, obj, job=None):
        job = job or PathUtils.findParentJob(obj)
        models = [m for m in (job.Model.Group if job is not None else []) if hasattr(m, "Shape")]
        if models:
            return max(m.Shape.BoundBox.ZMax for m in models)
        return job.Stock.Shape.BoundBox.ZMax if job is not None else 0.0

    def auto_min_diameter(self, obj):
        '''The selected face's inner edge, when the part is there just in front
        of the face inside it (a shoulder behind a smaller diameter); otherwise
        none (a front face, or one round a hole not drilled yet).'''
        import Part
        picked = self.selected_face(obj)
        if picked is None:
            return 0.0
        base, face = picked
        z = face.BoundBox.ZMax
        circles = [e.Curve.Radius for e in face.Edges if isinstance(e.Curve, Part.Circle) and e.Curve.Radius > 1e-6]
        if len(circles) < 2:
            return 0.0
        r_in = min(circles)
        probe = FreeCAD.Vector(max(r_in - 0.01, 0.0), 0, z + 0.01)
        if base.Shape.isInside(probe, 1e-6, True):
            return 2 * r_in
        return 0.0

    def op_generate_gcode(self, obj, turnTool):
        '''
        Generate GCode for the op
        '''
        # self.clear_path()
        facingOP = LLF.FaceOP()
        facingOP.set_params(self.getProps(obj))
        # down to Back (Z): the selected face, the part's front, or as set
        facingOP.set_params({'face_z': obj.FinalDepth.Value})

        stockBoundbox = PathTurnHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox)
        facingOP.add_stock(stockBoundbox)

        facingOP.add_part_edges(self.part_outline)
        facingOP.add_tool(turnTool)

        PathCode = facingOP.get_gcode()
        self.report_lathe_warnings(obj, facingOP)
        self.report_broken_edges(obj, facingOP)

        for command in PathCode:
            pathCommand = Path.Command(command.get_movement(), command.get_params())
            self.commandlist.append(pathCommand)

    # Back is the plane faced to: the selected face's, or the part's front
    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = self.part_front(obj, job)

    def opUpdateDepths(self, obj):
        obj.OpStartDepth = obj.OpStockZMax
        picked = self.selected_face(obj)
        obj.OpFinalDepth = picked[1].BoundBox.ZMax if picked is not None else self.part_front(obj)


def SetupProperties():
    setup = []
    setup.append("StepOver")
    setup.append("FinishPasses")
    setup.append("AllowGrooving")
    setup.append("StockToLeaveX")
    setup.append("StockToLeaveZ")
    return setup


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnFace operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnFace(obj, name, parentJob)
    return obj
