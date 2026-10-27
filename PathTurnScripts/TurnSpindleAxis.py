# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Put a Job's models and stock exactly on the spindle axis (Z).

A turned part must be round about the spindle axis. CAM's Job tools place
things by bounding boxes (a new cylinder stock on the model's, Center in XY
in the stock's, Set Origin on a face in the face's), and once a shape has
been drawn in the 3D view FreeCAD takes its bounding box from the display
mesh: a revolved surface is meshed from its seam, so the box comes out a few
microns lopsided in X, and so does whatever is placed by it. Here the axis
is found exactly instead: a model's from its circles round Z (the largest,
its turned diameter), else its exact bounding box; the stock's from its
exact bounding box. Only X and Y are moved, never Z.
"""

import math

import FreeCAD
import Part

translate = FreeCAD.Qt.translate

# an offset below this is rounding, not a misplaced part
EXACT = 1e-6


def exact_centre(shape):
    """The centre (x, y) of a shape's exact bounding box (not the display mesh's)."""
    bb = shape.optimalBoundingBox(False, False)
    return bb.Center.x, bb.Center.y


def model_axis(shape):
    """(x, y) of a model's turning axis: the centre of its largest circle round
    Z (its turned diameter; holes off the axis are smaller), else the centre
    of its exact bounding box."""
    best = None
    for edge in shape.Edges:
        try:
            curve = edge.Curve
        except Exception:      # some edges have no curve type
            continue
        if isinstance(curve, Part.Circle) and abs(abs(curve.Axis.z) - 1) < 1e-9:
            if best is None or curve.Radius > best.Radius:
                best = curve
    if best is not None:
        return best.Location.x, best.Location.y
    return exact_centre(shape)


def computed_stock(stock):
    """True for stock that works its own shape out from the models' bounding
    box on every recompute (Create from base): it cannot be placed."""
    try:
        import Path.Main.Stock as PathStock
        return PathStock.StockType.FromStock(stock) == PathStock.StockType.FromBase
    except Exception:
        return False


def offsets(job):
    """[(object, dx, dy)] of the Job's models and stock off the spindle axis
    by more than rounding."""
    out = []
    for model in getattr(getattr(job, "Model", None), "Group", None) or []:
        shape = getattr(model, "Shape", None)
        if shape is None or shape.isNull():
            continue
        dx, dy = model_axis(shape)
        if math.hypot(dx, dy) > EXACT:
            out.append((model, dx, dy))
    stock = getattr(job, "Stock", None)
    shape = getattr(stock, "Shape", None)
    if shape is not None and not shape.isNull():
        dx, dy = exact_centre(shape)
        if math.hypot(dx, dy) > EXACT:
            out.append((stock, dx, dy))
    return out


def put_on_axis(job):
    """Move the Job's models and stock (X and Y only) onto the spindle axis.
    Returns (moved labels, labels that could not be moved)."""
    moved, left = [], []
    for obj, dx, dy in offsets(job):
        if obj == getattr(job, "Stock", None) and computed_stock(obj):
            left.append(obj.Label)
            continue
        placement = obj.Placement
        placement.Base = placement.Base - FreeCAD.Vector(dx, dy, 0)
        obj.Placement = placement
        moved.append("{} ({:+.4f}, {:+.4f})".format(obj.Label, -dx, -dy))
    job.Document.recompute()
    return moved, left


def report_off_axis(obj, job):
    """For an operation's recompute: an error naming each of the Job's models
    and stock off the spindle axis, and the command that puts them on it
    (the operation still makes its path)."""
    for thing, dx, dy in offsets(job):
        FreeCAD.Console.PrintError(translate(
            "PathTurn",
            "{}: {} is {:.4f} mm off the spindle axis (centre at {:+.4f}, {:+.4f}): a turned part must be round "
            "about the axis. Use Turning > Put on spindle axis (CAM's Center in XY, Set Origin on a face and new "
            "stock place by bounding boxes FreeCAD takes from the display mesh, a few microns off)\n").format(
                obj.Label, thing.Label, math.hypot(dx, dy), dx, dy))


def job_for_selection():
    """The Job of the selected object, else the document's only Job."""
    import FreeCADGui
    import PathScripts.PathUtils as PathUtils
    for sel in FreeCADGui.Selection.getSelection():
        if hasattr(sel, "Operations") and hasattr(sel, "Model"):
            return sel
        job = PathUtils.findParentJob(sel)
        if job is not None:
            return job
    doc = FreeCAD.ActiveDocument
    jobs = [o for o in (doc.Objects if doc else []) if hasattr(o, "Operations") and hasattr(o, "Model")]
    return jobs[0] if len(jobs) == 1 else None


class CommandTurnSpindleAxis:
    """Put the Job's models and stock exactly on the spindle axis."""

    def GetResources(self):
        from PySide import QtCore
        return {
            "Pixmap": "CAM-TurnSpindleAxis",
            "MenuText": QtCore.QT_TRANSLATE_NOOP("CAM_TurnSpindleAxis", "Put on Spindle Axis"),
            "ToolTip": QtCore.QT_TRANSLATE_NOOP(
                "CAM_TurnSpindleAxis",
                "Move the Job's models and stock in X and Y so they are exactly round about the spindle axis (Z): "
                "a model by its turned diameter's circle, the stock by its exact bounding box. Select the Job (or "
                "anything in it) first if the document has more than one"),
        }

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and any(hasattr(o, "Operations") and hasattr(o, "Model") for o in doc.Objects)

    def Activated(self):
        import FreeCADGui
        from PySide import QtGui
        job = job_for_selection()
        title = translate("CAM_TurnSpindleAxis", "Put on Spindle Axis")
        if job is None:
            QtGui.QMessageBox.information(FreeCADGui.getMainWindow(), title, translate(
                "CAM_TurnSpindleAxis", "Select the Job (or anything in it) to put on the spindle axis"))
            return
        job.Document.openTransaction(title)
        try:
            moved, left = put_on_axis(job)
        finally:
            job.Document.commitTransaction()
        lines = []
        if moved:
            lines.append(translate("CAM_TurnSpindleAxis", "Moved onto the spindle axis (by X, Y):") + "\n  " + "\n  ".join(moved))
        if left:
            lines.append(translate(
                "CAM_TurnSpindleAxis",
                "Not moved: {} works its shape out from the models' bounding box on every recompute (Create from "
                "base). Use cylinder stock for turning, then run this again").format(", ".join(left)))
        if not lines:
            lines.append(translate("CAM_TurnSpindleAxis", "{}: the models and stock are already on the spindle axis").format(job.Label))
        QtGui.QMessageBox.information(FreeCADGui.getMainWindow(), title, "\n\n".join(lines))


if FreeCAD.GuiUp:
    import FreeCADGui
    FreeCADGui.addCommand("CAM_TurnSpindleAxis", CommandTurnSpindleAxis())
