# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Thread: single-point threading with a threading insert (Threading
shape), external or internal, on the cylindrical face selected on the Z
Range page. The selection gives the thread's length (its Z range) and the
diameter it is cut from; whether it is internal or external follows from
the face (a bore is internal) unless set by hand.

Standard threads (ISO metric coarse and fine, UNC, UNF) fill in the pitch
and depth; Custom takes them as entered. The passes are made by liblathe's
ThreadOP: explicit G33 passes by default, which only need
spindle-synchronized motion, or one G76 cycle on controls that have it.
"""

import math

import FreeCAD
import Path
import PathTurnScripts.PathTurnBase as PathTurnBase
import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers
import PathTurnScripts.ThreadData as ThreadData
from PySide import QtCore

import liblathe.op.thread as LLT


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


# spindle-synchronized commands, which posts do not list by default
SYNCHRONIZED = ("G33", "G76")
ALLOW_UNSUPPORTED = "allow_unsupported"   # CAM's Constants.ANNOT_ALLOW_UNSUPPORTED

INFEEDS = (("Modified flank (29.5\u00b0)", 29.5), ("Flank (30\u00b0)", 30.0), ("Radial", 0.0))
THREAD_TYPES = ("From the selection", "External", "Internal")


class ObjectTurnThread(PathTurnBase.ObjectOp):
    '''Proxy class for turning thread operations.'''

    uses_threading_tool = True

    def opFeatures(self, obj):
        '''Turning features plus base geometry: the selected face is the thread.'''
        PathOp = PathTurnBase.PathOp
        return (super().opFeatures(obj)
                | PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges | PathOp.FeatureBaseModels)

    def initOperation(self, obj):
        super().initOperation(obj)
        self.add_thread_properties(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        if not hasattr(obj, "ThreadStandard"):
            self.add_thread_properties(obj)
        for prop, tip in (("PassSchedule", "The passes the thread is cut in (read only)"),
                          ("SizeWarning", "How the selected diameter does not fit the thread size, if it does not (read only)")):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Thread", translate("TurnPath", tip))
                obj.setEditorMode(prop, 1)

    def add_thread_properties(self, obj):
        group = "Thread"
        add = obj.addProperty
        add("App::PropertyEnumeration", "ThreadStandard", group, translate("TurnPath", "Thread standard, or Custom"))
        add("App::PropertyEnumeration", "ThreadSize", group, translate("TurnPath", "Thread size in the standard"))
        add("App::PropertyEnumeration", "ThreadType", group,
            translate("TurnPath", "External or internal; from the selection: a bore is internal"))
        add("App::PropertyLength", "Pitch", group, translate("TurnPath", "Thread pitch (from the standard unless Custom)"))
        add("App::PropertyLength", "ThreadDepth", group,
            translate("TurnPath", "Radial depth to the insert's theoretical sharp point: for a standard thread from the "
                                  "selected diameter to the standard's root (or major, internal); entered for Custom"))
        add("App::PropertyLength", "ThreadDiameter", group,
            translate("TurnPath", "Diameter the thread is cut from: the selected diameter (read only)"))
        add("App::PropertyInteger", "Passes", group,
            translate("TurnPath", "Infeed passes to full depth; 0 uses the recommended number for the pitch"))
        add("App::PropertyLength", "FirstPassDepth", group,
            translate("TurnPath", "Depth of the first pass; 0 sets it from the number of passes"))
        add("App::PropertyLength", "MinPassDepth", group, translate("TurnPath", "Smallest depth increase per pass"))
        add("App::PropertyFloat", "Degression", group,
            translate("TurnPath", "How pass depths decrease: 2 removes the same area each pass, 1 the same depth"))
        add("App::PropertyEnumeration", "Infeed", group,
            translate("TurnPath", "How the insert feeds in: along the flank (29.5 or 30 degrees) or straight in"))
        add("App::PropertyInteger", "SpringPasses", group, translate("TurnPath", "Passes repeated at full depth"))
        add("App::PropertyLength", "LeadIn", group,
            translate("TurnPath", "Distance in front of the thread each pass starts at, for Z to reach speed; 0 is three pitches"))
        add("App::PropertyLength", "ThreadLength", group,
            translate("TurnPath", "Length of the thread from the front of the selected diameter; 0 threads its whole length"))
        add("App::PropertyString", "PassSchedule", group,
            translate("TurnPath", "The passes the thread is cut in (read only)"))
        add("App::PropertyString", "SizeWarning", group,
            translate("TurnPath", "How the selected diameter does not fit the thread size, if it does not (read only)"))
        add("App::PropertyBool", "UseG76", group,
            translate("TurnPath", "Output one G76 threading cycle (controls that have it) instead of explicit G33 passes"))
        obj.setEditorMode("ThreadDiameter", 1)
        obj.setEditorMode("PassSchedule", 1)
        obj.setEditorMode("SizeWarning", 1)

        # only write here: the Job dialog shows op defaults from a prototype
        # that does not read properties back
        standard, size = ThreadData.STANDARDS[0], "M12"
        obj.ThreadStandard = list(ThreadData.STANDARDS)
        obj.ThreadSize = ThreadData.sizes(standard)
        obj.ThreadSize = size
        obj.ThreadType = list(THREAD_TYPES)
        obj.Infeed = [name for name, _ in INFEEDS]
        _, pitch = ThreadData.lookup(standard, size)
        obj.Pitch = FreeCAD.Units.Quantity(pitch, FreeCAD.Units.Length)
        obj.ThreadDepth = FreeCAD.Units.Quantity(ThreadData.depth(pitch, False), FreeCAD.Units.Length)
        obj.Passes = 0
        obj.MinPassDepth = FreeCAD.Units.Quantity(0.05, FreeCAD.Units.Length)
        obj.Degression = 2.0
        obj.SpringPasses = 1
        obj.setEditorMode("Pitch", 1)
        obj.setEditorMode("ThreadDepth", 1)

    def update_sizes(self, obj):
        names = ThreadData.sizes(obj.ThreadStandard) or ["-"]
        current = obj.ThreadSize if hasattr(obj, "ThreadSize") else None
        obj.ThreadSize = names
        if current in names:
            obj.ThreadSize = current

    def internal(self, obj):
        if obj.ThreadType == THREAD_TYPES[2]:
            return True
        if obj.ThreadType == THREAD_TYPES[1]:
            return False
        face = self.selected_face(obj)
        return face is not None and _is_bore(face)

    def apply_standard(self, obj):
        '''Pitch and depth from the standard (not for Custom).'''
        found = ThreadData.lookup(obj.ThreadStandard, obj.ThreadSize)
        custom = found is None
        for prop in ("Pitch", "ThreadDepth"):
            obj.setEditorMode(prop, 0 if custom else 1)
        if not custom:
            _, pitch = found
            obj.Pitch = FreeCAD.Units.Quantity(pitch, FreeCAD.Units.Length)
            obj.ThreadDepth = FreeCAD.Units.Quantity(ThreadData.depth(pitch, self.internal(obj)), FreeCAD.Units.Length)

    def onChanged(self, obj, prop):
        # while a document is restored, properties arrive one at a time: the
        # standard's pitch and depth were saved with it, nothing to update
        restoring = "Restore" in getattr(obj, "State", []) or getattr(getattr(obj, "Document", None), "Restoring", False)
        needed = all(hasattr(obj, p) for p in ("ThreadStandard", "ThreadSize", "ThreadType", "Pitch", "ThreadDepth"))
        if restoring or not needed:
            super().onChanged(obj, prop)
            return
        if prop == "ThreadStandard":
            self.update_sizes(obj)
            self.apply_standard(obj)
        elif prop in ("ThreadSize", "ThreadType"):
            self.apply_standard(obj)
        super().onChanged(obj, prop)

    def selected_face(self, obj):
        for base, subs in (getattr(obj, "Base", None) or []):
            for sub in subs:
                if sub.startswith("Face"):
                    face = base.Shape.getElement(sub)
                    if isinstance(face.Surface, _cylinder_type()):
                        return face
        return None

    def op_generate_gcode(self, obj, tool):
        '''Thread the selected cylindrical face with liblathe's ThreadOP.'''
        face = self.selected_face(obj)
        if face is None:
            raise RuntimeError(translate('PathTurn', "Select the diameter to thread (its cylindrical face) on the Z Range page"))
        internal = self.internal(obj)
        # an external thread is cut from the surface as the turning
        # operations see it: the part's outline (a section on +X), which also
        # places the thread's radius exactly where the clearance checks look,
        # even for a model a hair off the axis. The outline has no bores, so an
        # internal thread keeps the bore face's radius.
        radius = face.Surface.Radius if internal else self.outline_radius(face) or face.Surface.Radius
        obj.ThreadDiameter = FreeCAD.Units.Quantity(2 * radius, FreeCAD.Units.Length)
        self.apply_standard(obj)
        found = ThreadData.lookup(obj.ThreadStandard, obj.ThreadSize)
        if found is not None:
            # a standard thread is cut to the standard's root (external) or
            # major (internal) diameter, whatever the surface was turned or
            # bored to: the depth is from the surface to there
            major, pitch = found
            target = ThreadData.target_diameter(major, pitch, internal) / 2
            depth = (target - radius) if internal else (radius - target)
            if depth <= 1e-6:
                raise RuntimeError(translate('PathTurn',
                    "The selected diameter ({:.3f}) is already at or past the thread's {} diameter ({:.3f})").format(
                        2 * radius, "major" if internal else "root", 2 * target))
            obj.ThreadDepth = FreeCAD.Units.Quantity(depth, FreeCAD.Units.Length)
            problem = ThreadData.size_problem(major, pitch, internal, 2 * radius)
        else:
            problem = None
        warning = ""
        if problem:
            warning = "The selected diameter ({:.3f}) is {} of {} {}".format(
                2 * radius, problem, obj.ThreadStandard, obj.ThreadSize)
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))
        if obj.SizeWarning != warning:
            obj.SizeWarning = warning

        op = LLT.ThreadOP()
        op.set_params(self.getProps(obj))
        op.set_params({
            'pitch': obj.Pitch.Value,
            'thread_depth': obj.ThreadDepth.Value,
            'thread_radius': radius,
            'internal': internal,
            'passes': obj.Passes,
            'first_depth': obj.FirstPassDepth.Value,
            'min_depth': obj.MinPassDepth.Value,
            'degression': obj.Degression,
            'infeed_angle': dict(INFEEDS).get(obj.Infeed, 29.5),
            'spring_passes': obj.SpringPasses,
            'lead_in': obj.LeadIn.Value,
            'canned': obj.UseG76,
            'thread_length': obj.ThreadLength.Value,
            'tool_angle': tool.ProfileAngle.Value,
            'tool_width': tool.Width.Value if hasattr(tool, "Width") else 0.0,
        })
        op.add_stock(PathTurnHelpers.getliblatheBoundBox(self.stock_silhoutte.BoundBox))
        op.add_part_edges(self.part_outline)

        for command in op.get_gcode():
            name = command.get_movement()
            if name in SYNCHRONIZED:
                # posts accept only the commands their machine lists; G33 and
                # G76 are not in CAM's default list, so mark them to be passed
                # through as they are
                self.commandlist.append(Path.Command(name, command.get_params(), {ALLOW_UNSUPPORTED: True}))
            else:
                self.commandlist.append(Path.Command(name, command.get_params()))
        for warning in getattr(op, "warnings", []):
            FreeCAD.Console.PrintWarning("{}: {}\n".format(obj.Label, warning))
        depths = getattr(op, "depths", [])
        if depths:
            n = len(depths) - max(0, int(obj.SpringPasses))
            cuts = [b - a for a, b in zip([0.0] + depths[:n - 1], depths[:n])]
            schedule = "{} passes{}: first {:.3f}, last {:.3f} deep; to {} {:.3f}".format(
                n, " + {} spring".format(obj.SpringPasses) if obj.SpringPasses else "", cuts[0], cuts[-1],
                "diameter" if internal else "root diameter",
                2 * (radius + depths[-1]) if internal else 2 * (radius - depths[-1]))
            if obj.PassSchedule != schedule:
                obj.PassSchedule = schedule
        if obj.UseG76 and dict(INFEEDS).get(obj.Infeed, 29.5) > 0:
            FreeCAD.Console.PrintWarning(
                "{}: CAM's posts currently drop G76's Q word (the infeed angle): the control then feeds in "
                "radially. Check the posted G76 line, or use the explicit passes (Use G76 cycle off)\n".format(obj.Label))

    def outline_radius(self, face):
        '''The part outline's radius at the middle of a face's Z range, or None.'''
        z = (face.BoundBox.ZMin + face.BoundBox.ZMax) / 2
        best = None
        for seg in getattr(self, "part_outline", None) or []:
            z1, z2 = seg.start.Z, seg.end.Z
            if abs(z2 - z1) < 1e-9 or not (min(z1, z2) - 1e-9 <= z <= max(z1, z2) + 1e-9):
                continue
            t = (z - z1) / (z2 - z1)
            r = -(seg.start.X + t * (seg.end.X - seg.start.X)) if seg.bulge == 0 else max(-seg.start.X, -seg.end.X)
            best = r if best is None else max(best, r)
        return best

    def opSetDefaultValues(self, obj, job):
        obj.OpStartDepth = job.Stock.Shape.BoundBox.ZMax
        obj.OpFinalDepth = job.Stock.Shape.BoundBox.ZMin

    def opUpdateDepths(self, obj):
        # the selected face is the thread: its Z range
        self.update_depths_from_base(obj)


def _cylinder_type():
    import Part
    return Part.Cylinder


def _is_bore(face):
    '''True when a cylindrical face faces the axis (a bore).'''
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    point, normal = face.valueAt(u, v), face.normalAt(u, v)
    axis = face.Surface.Axis
    centre = face.Surface.Center
    radial = point - centre
    radial = radial - axis * radial.dot(axis)
    return normal.dot(radial) < 0


def SetupProperties():
    return ["Passes", "MinPassDepth", "Degression", "Infeed", "SpringPasses", "LeadIn", "UseG76"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnThread operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnThread(obj, name, parentJob)
    return obj
