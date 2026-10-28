# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Turn Thread: single-point threading of the selected cylindrical face (its Z range and
diameter; a bore is internal) with liblathe's ThreadOP, as G33 passes or one G76 cycle."""

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


# Values the op works out unless set by hand: (switch, value, tooltip). Passes and
# First pass depth are alternatives (see EXCLUSIVE).
AUTO_VALUES = (
    ("SetThreadLength", "ThreadLength", "Set the thread length by hand; otherwise the whole selected diameter"),
    ("SetPasses", "Passes", "Set the number of infeed passes by hand; otherwise the recommended number for the pitch"),
    ("SetFirstPassDepth", "FirstPassDepth", "Set the first pass depth by hand; otherwise from the passes and the degression"),
    ("SetLeadIn", "LeadIn", "Set the lead-in by hand; otherwise three pitches, or less where the part in front leaves less room (a neck)"),
    ("SetRunOut", "RunOut", "Set the run-out by hand (0: stop dead, into a relief groove); otherwise one pitch"),
)
RUN_OUT_TIP = ("Run-out: over this last length of the thread (along Z) each pass tapers out to the crest, still "
               "synchronised with the spindle, instead of stopping dead at full depth (G76's E, with L2). 0 stops "
               "dead, for a thread ending in a relief groove. One pitch unless Set Run Out")
EXCLUSIVE = {"SetPasses": "SetFirstPassDepth", "SetFirstPassDepth": "SetPasses"}

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
        self.add_auto_switches(obj, migrate=True)
        self.add_tolerance_class(obj)
        for prop, tip in (("PassSchedule", "The passes the thread is cut in (read only)"),
                          ("SizeWarning", "How the selected diameter does not fit the thread size, if it does not (read only)")):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Thread", translate("TurnPath", tip))
                obj.setEditorMode(prop, 1)

    def add_tolerance_class(self, obj):
        '''ToleranceClass (and the ThreadReport), added to older ops too.'''
        if not hasattr(obj, "ToleranceClass"):
            obj.addProperty("App::PropertyEnumeration", "ToleranceClass", "Thread", translate(
                "TurnPath", "Tolerance class (from CAM's thread tables): the thread is cut so its pitch diameter is "
                            "in the middle of the class's range; Basic cuts the basic profile"))
            try:
                internal = self.internal(obj)
            except Exception:       # a Job dialog prototype: no selection
                internal = False
            obj.ToleranceClass = ThreadData.classes(getattr(obj, "ThreadStandard", "Metric coarse"), internal)
        if not hasattr(obj, "ThreadReport"):
            obj.addProperty("App::PropertyString", "ThreadReport", "Thread", translate(
                "TurnPath", "What the thread needs and how it is cut: diameters to turn or bore first, pitch "
                            "diameter, measurement over wires, root, passes, Z range (read only)"))
            obj.setEditorMode("ThreadReport", 1)

    def update_classes(self, obj):
        '''The classes on offer follow the standard and whether the thread is internal.'''
        if not hasattr(obj, "ToleranceClass"):
            return
        names = ThreadData.classes(obj.ThreadStandard, self.internal(obj))
        if list(obj.getEnumerationsOfProperty("ToleranceClass")) != names:
            current = obj.ToleranceClass
            obj.ToleranceClass = names
            obj.ToleranceClass = current if current in names else names[0]

    def add_auto_switches(self, obj, migrate=False):
        '''The Set* switches; on an older document a non-zero value was set by hand.'''
        # (also run on the Job dialog's operation prototypes, whose properties
        # cannot all be read back: hence the defaults)
        if not hasattr(obj, "RunOut"):
            obj.addProperty("App::PropertyLength", "RunOut", "Thread", translate("TurnPath", RUN_OUT_TIP))
            if migrate:
                # an op from before the run-out stopped dead: it still does
                # (set, at 0), so its program does not change
                obj.addProperty("App::PropertyBool", "SetRunOut", "Thread", translate("TurnPath", AUTO_VALUES[-1][2]))
                obj.SetRunOut = True
        for switch, prop, tip in AUTO_VALUES:
            if not hasattr(obj, switch):
                obj.addProperty("App::PropertyBool", switch, "Thread", translate("TurnPath", tip))
                value = getattr(obj, prop, 0)
                value = getattr(value, "Value", value) or 0
                setattr(obj, switch, bool(migrate and value > 0))
            obj.setEditorMode(prop, 0 if getattr(obj, switch, False) else 1)

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
            translate("TurnPath", "Infeed passes to full depth (the recommended number for the pitch unless Set Passes)"))
        add("App::PropertyLength", "FirstPassDepth", group,
            translate("TurnPath", "Depth of the first pass (from the passes and the degression unless Set First Pass Depth)"))
        add("App::PropertyLength", "MinPassDepth", group, translate("TurnPath", "Smallest depth increase per pass"))
        add("App::PropertyFloat", "Degression", group,
            translate("TurnPath", "How pass depths decrease: 1.5 (default) is gentle, with a light first pass; 2 removes the same area each pass, the first deepest; 1 the same depth each pass"))
        add("App::PropertyEnumeration", "Infeed", group,
            translate("TurnPath", "How the insert feeds in: along the flank (29.5 or 30 degrees) or straight in"))
        add("App::PropertyInteger", "SpringPasses", group, translate("TurnPath", "Passes repeated at full depth"))
        add("App::PropertyLength", "LeadIn", group,
            translate("TurnPath", "Distance in front of the thread each pass starts at, for Z to reach speed (three pitches unless Set Lead In, or less where the part in front of the thread leaves less room, e.g. a thread behind a neck)"))
        add("App::PropertyLength", "ThreadLength", group,
            translate("TurnPath", "Length of the thread from the front of the selected diameter (its whole length unless Set Thread Length)"))
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
        # 1.5, a gentler schedule than constant area (2): a lighter first pass,
        # closer to insert makers' tables and kinder to light machines
        obj.Degression = 1.5
        obj.SpringPasses = 1
        obj.setEditorMode("Pitch", 1)
        obj.setEditorMode("ThreadDepth", 1)
        self.add_auto_switches(obj)
        self.add_tolerance_class(obj)

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
        self.update_classes(obj)

    def onChanged(self, obj, prop):
        # while a document is restored, properties arrive one at a time: the
        # standard's pitch and depth were saved with it, nothing to update
        restoring = "Restore" in getattr(obj, "State", []) or getattr(getattr(obj, "Document", None), "Restoring", False)
        needed = all(hasattr(obj, p) for p in ("ThreadStandard", "ThreadSize", "ThreadType", "Pitch", "ThreadDepth"))
        if restoring or not needed:
            super().onChanged(obj, prop)
            return
        switches = {switch: value for switch, value, _ in AUTO_VALUES}
        if prop in switches and hasattr(obj, prop):
            obj.setEditorMode(switches[prop], 0 if getattr(obj, prop) else 1)
            other = EXCLUSIVE.get(prop)
            if getattr(obj, prop) and other and getattr(obj, other, False):
                setattr(obj, other, False)
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
        '''Thread the selected face; on failure the error replaces the page's report.'''
        try:
            self.generate_thread(obj, tool)
        except Exception as e:
            if getattr(obj, "ThreadReport", None) is not None and obj.ThreadReport:
                obj.ThreadReport = ""
            if obj.SizeWarning != str(e):
                obj.SizeWarning = str(e)
            raise

    def generate_thread(self, obj, tool):
        face = self.selected_face(obj)
        if face is None:
            raise RuntimeError(translate('PathTurn', "Select the diameter to thread (its cylindrical face) on the Z Range page"))
        internal = self.internal(obj)
        # external: the radius from the part's outline (where the clearance checks
        # look); internal: the bore face's, as the outline has no bores
        radius = face.Surface.Radius if internal else self.outline_radius(face) or face.Surface.Radius
        obj.ThreadDiameter = FreeCAD.Units.Quantity(2 * radius, FreeCAD.Units.Length)
        self.apply_standard(obj)
        found = ThreadData.lookup(obj.ThreadStandard, obj.ThreadSize)
        if found is not None:
            # a standard thread is cut to the standard's root (external) or
            # major (internal) diameter, whatever the surface was turned or
            # bored to: the depth is from the surface to there
            major, pitch = found
            # cut so the pitch diameter is in the middle of the class's range
            # (basic profile without class data)
            tol = ThreadData.tolerance(obj.ThreadStandard, obj.ThreadSize, internal, getattr(obj, "ToleranceClass", ThreadData.BASIC))
            target = ThreadData.class_target_diameter(major, pitch, internal, tol) / 2
            depth = (target - radius) if internal else (radius - target)
            if depth <= 1e-6:
                raise RuntimeError(translate('PathTurn',
                    "The selected diameter ({:.3f}) is already at or past the thread's {} diameter ({:.3f})").format(
                        2 * radius, "major" if internal else "root", 2 * target))
            obj.ThreadDepth = FreeCAD.Units.Quantity(depth, FreeCAD.Units.Length)
            problem = ThreadData.size_problem(major, pitch, internal, 2 * radius)
        else:
            problem, tol, major, pitch, target = None, None, None, obj.Pitch.Value, None
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
            'passes': obj.Passes if obj.SetPasses else 0,
            'first_depth': obj.FirstPassDepth.Value if obj.SetFirstPassDepth else 0.0,
            'min_depth': obj.MinPassDepth.Value,
            'degression': obj.Degression,
            'infeed_angle': dict(INFEEDS).get(obj.Infeed, 29.5),
            'spring_passes': obj.SpringPasses,
            'lead_in': obj.LeadIn.Value if obj.SetLeadIn else 0.0,
            'run_out': obj.RunOut.Value if getattr(obj, "SetRunOut", False) else pitch,
            'canned': obj.UseG76,
            'thread_length': obj.ThreadLength.Value if obj.SetThreadLength else 0.0,
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
            report = self.report(obj, internal, radius, major, pitch, tol, depths[-1], n, cuts,
                                 abs(op.z_drive - op.z_front), op.z_front, op.z_back, op.run_out)
            if getattr(obj, "ThreadReport", None) is not None and obj.ThreadReport != report:
                obj.ThreadReport = report
            used = {"Passes": n, "FirstPassDepth": cuts[0], "LeadIn": abs(op.z_drive - op.z_front),
                    "ThreadLength": abs(op.z_front - op.z_back), "RunOut": op.run_out}
            for switch, prop, _ in AUTO_VALUES:
                if getattr(obj, switch):
                    continue
                current = getattr(obj, prop)
                if prop == "Passes":
                    if current != used[prop]:
                        setattr(obj, prop, used[prop])
                elif abs(current.Value - used[prop]) > 1e-7:
                    setattr(obj, prop, FreeCAD.Units.Quantity(used[prop], FreeCAD.Units.Length))
        flank = dict(INFEEDS).get(obj.Infeed, 29.5) > 0
        run_out = (obj.RunOut.Value if getattr(obj, "SetRunOut", False) else obj.Pitch.Value) > 0
        if obj.UseG76 and (flank or run_out):
            lost = []
            if flank:
                lost.append("Q word (the infeed angle: the control then feeds in radially)")
            if run_out:
                lost.append("E word through a machine definition (the run-out: the control then pulls "
                            "straight out at the thread's end)")
            FreeCAD.Console.PrintWarning(
                "{}: CAM's own posts drop G76's {}. Post with the addon's linuxcnc_lathe post, which keeps them, "
                "or use the explicit passes (Use G76 cycle off)\n".format(obj.Label, "; and ".join(lost)))

    def report(self, obj, internal, radius, major, pitch, tol, depth, n, cuts, lead, z_front, z_back, run_out=0.0):
        '''What the thread needs and how it is cut, for the page: one item a
        line. A Unified thread's dimensions are in inches, as it is specified;
        positions along Z are in the document's units (machine coordinates).'''
        inch = obj.ThreadStandard in ("UNC", "UNF")

        def dim(mm, places=None):
            if inch:
                return "{:.{p}f}\"".format(mm / 25.4, p=4 if places is None else places)
            return "{:.{p}f}".format(mm, p=3 if places is None else places)

        def pos(mm):
            return FreeCAD.Units.Quantity(mm, FreeCAD.Units.Length).UserString

        d = 2 * radius
        name = "{} {}".format(obj.ThreadStandard, obj.ThreadSize) if major else "Custom thread, pitch {:.3f}".format(pitch)
        cls = getattr(obj, "ToleranceClass", ThreadData.BASIC)
        lines = ["{} {}{}".format(name, "internal" if internal else "external",
                                  ", class {}".format(cls) if tol else "")]

        def against(lo, hi):
            if d > hi + 1e-4:
                return "the selected {} is {} over".format(dim(d), dim(d - hi))
            if d < lo - 1e-4:
                return "the selected {} is {} under".format(dim(d), dim(lo - d))
            return "the selected {} is within".format(dim(d))

        if tol:
            if internal:
                lines.append("Bore the minor diameter to {}-{} first: {}".format(
                    dim(tol["minor_min"]), dim(tol["minor_max"]), against(tol["minor_min"], tol["minor_max"])))
            else:
                lines.append("Turn the major diameter to {}-{} first: {}".format(
                    dim(tol["major_min"]), dim(tol["major_max"]), against(tol["major_min"], tol["major_max"])))
            mid = (tol["pitch_min"] + tol["pitch_max"]) / 2
            lines.append("Pitch diameter {}-{}, cut to {}".format(dim(tol["pitch_min"]), dim(tol["pitch_max"]), dim(mid)))
            if not internal:
                w, add = ThreadData.best_wire(pitch)
                lines.append("Over three best-size wires (dia {}): {}-{}".format(
                    dim(w, 5 if inch else 4), dim(tol["pitch_min"] + add), dim(tol["pitch_max"] + add)))
        elif major:
            reason = "Basic profile chosen" if cls == ThreadData.BASIC else "No {} data for this size".format(cls)
            lines.append("{}: cut to the basic profile (pitch diameter {})".format(
                reason, dim(ThreadData.basic_pitch_diameter(major, pitch))))
        lines.append("{} {}, {} deep from the selected diameter".format(
            "Major diameter" if internal else "Root diameter", dim(d + 2 * depth if internal else d - 2 * depth), dim(depth)))
        lines.append("{} passes{}: first {}, last {}".format(
            n, " + {} spring".format(obj.SpringPasses) if obj.SpringPasses else "", dim(cuts[0]), dim(cuts[-1])))
        lines.append("Z {} to {} ({} long); each pass starts {} in front".format(
            pos(z_front), pos(z_back), pos(abs(z_front - z_back)), pos(lead)))
        if run_out > 0:
            lines.append("Full depth to Z {}, then a run-out ({} long) out to the crest at Z {}".format(
                pos(z_back + run_out), pos(run_out), pos(z_back)))
        else:
            lines.append("No run-out: the passes stop dead at Z {} (a relief groove there)".format(pos(z_back)))
        return "\n".join(lines)

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
    return ["Passes", "MinPassDepth", "Degression", "Infeed", "SpringPasses", "LeadIn", "RunOut", "UseG76"]


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a TurnThread operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnThread(obj, name, parentJob)
    return obj
