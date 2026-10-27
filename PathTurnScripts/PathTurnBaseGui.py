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
import FreeCADGui
import Path.Log as PathLog
import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.Selection as PathSelection
import Path.Preferences
#import PathGui

import Path.Base.Gui.Util as PathGuiUtil

from PySide import QtCore, QtGui

import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers

__title__ = "Path Turn Base Gui"
__author__ = "dubstar-04 (Daniel Wood)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Base class Gui implementation for turning operations."

LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.NOTICE, PathLog.thisModule())


# --- selection gate -------------------------------------------------------
# CAM picks the selection gate for an operation from a fixed table of names
# (Path.Op.Gui.Selection.select). It lists the original turning operations,
# but sends them to TURNGate, which only accepts what CAM's drilling test
# considers a hole, and raises "expected a Face or Edge. Got a Vertex" for
# every vertex under the pointer; TurnGroove is not listed at all (KeyError).
# The turning operations use the selection for its Z extent, and accept
# faces, edges and whole objects, so give them a gate that allows exactly
# that.

TURNING_OPS = ("TurnDrill", "TurnChamfer", "TurnGrooveTurn", "TurnFace", "TurnProfile", "TurnPartoff", "TurnRough", "TurnGroove", "TurnThread")


# Everything a page caches that refers to its widgets. Qt deletes the widgets
# when the panel closes; a Python reference kept past that leaves PySide with
# a wrapper for freed memory, which it can then hand out for a new object at
# the same address (seen as a widget of the wrong type, or a crash). Pages
# drop these in cleanupPage, which CAM calls before the panel is destroyed.
CACHED_WIDGETS = ("_limits", "_limit_buttons", "_cl_boxes", "_diagram", "_lead_box", "_gboxes", "_quantity_boxes", "_boxes",
                  "rangeLabel")


def release_widgets(page):
    for name in CACHED_WIDGETS:
        if name in vars(page):
            setattr(page, name, None)


class TurningGate:
    """Allow faces, edges, vertices and whole objects with a shape (a vertex
    for the arrow buttons: its Z on the Z Range page, its diameter on the
    Diameters page)."""

    def allow(self, doc, obj, sub):
        if not hasattr(obj, "Shape"):
            return False
        if not sub:
            return True
        return sub.startswith("Face") or sub.startswith("Edge") or sub.startswith("Vertex")


def turning_select():
    FreeCADGui.Selection.addSelectionGate(TurningGate())
    if not Path.Preferences.suppressSelectionModeWarning():
        FreeCAD.Console.PrintWarning("Turning Select Mode\n")


if not getattr(PathSelection.select, "_turning", False):
    _cam_select = PathSelection.select

    def _select(op):
        if op in TURNING_OPS:
            return turning_select
        return _cam_select(op)

    _select._turning = True
    PathSelection.select = _select


class TaskPanelTurnBaseGeometryPage(PathOpGui.TaskPanelBaseGeometryPage):
    '''
    CAM's Base Geometry page, titled "Z Range", with a note explaining how
    the turning operations use the selection (only for its extent along Z)
    and a line showing the resulting front and back and which faces set
    them.
    '''

    def cleanupPage(self, obj):
        release_widgets(self)
        super().cleanupPage(obj)

    NOTE = QtCore.QT_TRANSLATE_NOOP(
        "PathTurn",
        "Turning uses the selection only for its position along the Z axis: the "
        "operation is limited to the Z range from the front-most to the back-most "
        "selected face, edge or object (e.g. a sketch or wire), and everything in that "
        "range is turned, including geometry between them that is not selected. With "
        "nothing selected, the operation covers the whole stock. Front and Back below "
        "show the range used; tick either to set it by hand.")

    CORNER_NOTE = QtCore.QT_TRANSLATE_NOOP(
        "PathTurn",
        "Select the circular edges of the corners to chamfer or fillet (circles round the spindle axis). Only "
        "sharp outside corners between two straight edges can be; the others are reported and left alone.")

    def getTitle(self, obj):
        if getattr(getattr(obj, "Proxy", None), "selects_corners", False):
            return FreeCAD.Qt.translate("PathTurn", "Edges")
        return FreeCAD.Qt.translate("PathTurn", "Z Range")

    def modifyPanel(self, panel):
        super().modifyPanel(panel)
        corners = getattr(getattr(self.obj, "Proxy", None), "selects_corners", False)
        label = QtGui.QLabel(FreeCAD.Qt.translate("PathTurn", self.CORNER_NOTE if corners else self.NOTE))
        label.setWordWrap(True)
        label.setObjectName("turningBaseGeometryNote")
        # the resulting front and back, updated whenever the list changes
        self.rangeLabel = QtGui.QLabel()
        self.rangeLabel.setWordWrap(True)
        self.rangeLabel.setObjectName("turningBaseGeometryRange")
        limits = self.make_limits()
        layout = panel.layout()
        if layout is None:
            return
        if hasattr(layout, "insertWidget"):
            # box layout: put the note, the range and the limits first
            layout.insertWidget(0, label)
            layout.insertWidget(1, self.rangeLabel)
            if limits is not None:
                layout.insertWidget(2, limits)
        else:
            # grid layout: add them below the existing widgets, full width
            columns = max(1, layout.columnCount())
            layout.addWidget(label, layout.rowCount(), 0, 1, columns)
            layout.addWidget(self.rangeLabel, layout.rowCount(), 0, 1, columns)
            if limits is not None:
                layout.addWidget(limits, layout.rowCount(), 0, 1, columns)

    # The Z range's two ends, worked out unless set, as the diameters are:
    # CAM ties StartDepth / FinalDepth to OpStartDepth / OpFinalDepth (the
    # selection's extent, or the op's defaults) by an expression; ticking
    # an end removes it and the value is the user's, unticking restores it.
    # (property, checkbox text, tooltip)
    LIMITS = (
        ("StartDepth", "Front (Z)",
         "The front of the Z range. Unticked: the selection's front, or without one the op's own (the stock's "
         "front), shown greyed out. Ticked: this value, whatever is selected"),
        ("FinalDepth", "Back (Z)",
         "The back of the Z range. Unticked: the selection's back, or without one the op's own (e.g. the part's "
         "back), shown greyed out. Ticked: this value, whatever is selected"),
    )

    ARROW_TIPS = {
        "StartDepth": "Transfer the Z of the selected feature as the front: a vertex, a flat face or circular edge, "
                      "or the front end of a cylinder, cone or object",
        "FinalDepth": "Transfer the Z of the selected feature as the back: a vertex, a flat face or circular edge, "
                      "or the back end of a cylinder, cone or object",
    }

    def _limits_shown(self):
        '''The ends an op uses: none for Turn Thread (its own thread length),
        only the back for Turn Partoff (where it parts).'''
        proxy = getattr(self.obj, "Proxy", None)
        if getattr(proxy, "uses_threading_tool", False) or getattr(proxy, "selects_corners", False):
            return ()
        if type(proxy).__name__ == "ObjectTurnPart":
            return ("FinalDepth",)
        return ("StartDepth", "FinalDepth")

    def make_limits(self):
        shown = self._limits_shown()
        if not shown:
            return None
        box = QtGui.QWidget()
        grid = QtGui.QGridLayout(box)
        grid.setContentsMargins(0, 4, 0, 0)
        loader = FreeCADGui.UiLoader()
        self._limits = {}
        self._limit_buttons = {}
        for row, (prop, text, tip) in enumerate(l for l in self.LIMITS if l[0] in shown):
            check = QtGui.QCheckBox(FreeCAD.Qt.translate("PathTurn", text))
            check.setToolTip(FreeCAD.Qt.translate("PathTurn", tip))
            spin = loader.createWidget("Gui::QuantitySpinBox")
            spin.setToolTip(check.toolTip())
            spin.setProperty("minimum", -1.0e6)
            spin.setProperty("maximum", 1.0e6)
            # the arrow, as on CAM's Depths page and the Diameters page:
            # the selected feature's Z into the field (and ticked)
            arrow = QtGui.QToolButton()
            arrow.setIcon(QtGui.QIcon(":/icons/button_left.svg"))
            arrow.setToolTip(FreeCAD.Qt.translate("PathTurn", self.ARROW_TIPS[prop]))
            arrow.setEnabled(False)
            grid.addWidget(check, row, 0)
            grid.addWidget(spin, row, 1)
            grid.addWidget(arrow, row, 2)
            bound = PathGuiUtil.QuantitySpinBox(spin, self.obj, prop)
            check.toggled.connect(lambda on, p=prop: self.set_limit(p, on))
            spin.editingFinished.connect(lambda p=prop: self.limit_edited(p))
            arrow.clicked.connect(lambda _=False, p=prop: self.limit_from_selection(p))
            self._limits[prop] = (check, spin, bound)
            self._limit_buttons[prop] = arrow
        self.refresh_limits()
        return box

    def _is_set(self, prop):
        return prop not in dict(self.obj.ExpressionEngine or [])

    def set_limit(self, prop, on):
        '''Ticked: the value is the user's (the expression goes); unticked:
        back to the worked-out one.'''
        check, spin, bound = self._limits[prop]
        spin.setEnabled(on)
        if on and not self._is_set(prop):
            value = getattr(self.obj, prop).Value
            self.obj.setExpression(prop, None)
            setattr(self.obj, prop, FreeCAD.Units.Quantity(value, FreeCAD.Units.Length))
        elif not on and self._is_set(prop):
            self.obj.setExpression(prop, "Op" + prop)
            self.obj.recompute()
        # the change is the op's now: the panel's Apply (and OK) recompute it
        self.setDirty()
        self.refresh_limits()

    @staticmethod
    def _end(prop):
        return "front" if prop == "StartDepth" else "back"

    def limit_from_selection(self, prop):
        '''The selected feature's Z as this end of the range: a value taken
        from the model is set by hand, so the end is ticked.'''
        z = selection_z(FreeCADGui.Selection.getSelectionEx(), self._end(prop))
        if z is None or prop not in (getattr(self, "_limits", None) or {}):
            return
        check, spin, bound = self._limits[prop]
        if not self._is_set(prop):
            self.set_limit(prop, True)
        bound.updateWidget(FreeCAD.Units.Quantity(z, FreeCAD.Units.Length))
        if bound.updateProperty():
            self.setDirty()
        self.refresh_limits()

    def updateSelection(self, obj, sel):
        super().updateSelection(obj, sel)
        for prop, arrow in (getattr(self, "_limit_buttons", None) or {}).items():
            arrow.setEnabled(selection_z(sel, self._end(prop)) is not None)

    def limit_edited(self, prop):
        check, spin, bound = self._limits[prop]
        if check.isChecked():
            if bound.updateProperty():
                self.setDirty()
            self.updateRangeLabel()

    def refresh_limits(self):
        for prop, (check, spin, bound) in (getattr(self, "_limits", None) or {}).items():
            on = self._is_set(prop)
            check.blockSignals(True)
            check.setChecked(on)
            check.blockSignals(False)
            spin.setEnabled(on)
            bound.updateWidget()
        self.updateRangeLabel()

    def updateData(self, obj, prop):
        if prop in ("StartDepth", "FinalDepth", "OpStartDepth", "OpFinalDepth", "ExpressionEngine"):
            self.refresh_limits()

    def rangeText(self):
        '''The front and back of the selection, and which faces set them.'''
        front = back = None
        for base_obj, subs in (getattr(self.obj, "Base", None) or []):
            for sub in (subs or [""]):
                try:
                    shape = base_obj.Shape.getElement(sub) if sub else base_obj.Shape
                except Exception:
                    continue
                bb = shape.BoundBox
                name = sub or base_obj.Label
                if front is None or bb.ZMax > front[0]:
                    front = (bb.ZMax, name)
                if back is None or bb.ZMin < back[0]:
                    back = (bb.ZMin, name)
        set_ends = [n for p, n in (("StartDepth", "front"), ("FinalDepth", "back")) if p in (getattr(self, "_limits", None) or {}) and self._is_set(p)]
        note = ("\n" + FreeCAD.Qt.translate("PathTurn", "Set by hand: the {} (below).").format(" and ".join(set_ends))) if set_ends else ""
        if front is None:
            return FreeCAD.Qt.translate("PathTurn", "Nothing selected: the op's own range.") + note

        def z(value):
            return FreeCAD.Units.Quantity(value, FreeCAD.Units.Length).UserString

        text = FreeCAD.Qt.translate("PathTurn", "Front: Z {} ({})    Back: Z {} ({})").format(
            z(front[0]), front[1], z(back[0]), back[1])
        if front[0] - back[0] <= 1e-4:
            text += "\n" + FreeCAD.Qt.translate(
                "PathTurn",
                "The selection has no length along Z: select geometry at two different Z positions.")
        return text + note

    def updateRangeLabel(self):
        label = getattr(self, "rangeLabel", None)
        if label is not None:
            label.setText(self.rangeText())

    # the list is refreshed through these; update the range after each
    def setFields(self, obj):
        super().setFields(obj)
        self.refresh_limits()
        self.updateRangeLabel()

    def updateBase(self):
        super().updateBase()
        self.updateRangeLabel()

    def clearBase(self):
        super().clearBase()
        self.updateRangeLabel()


class SvgDiagram(QtGui.QLabel):
    """
    An SVG drawn at the label's width (the height follows the drawing's
    proportions), redrawn when the panel is resized, at the screen's pixel
    ratio: it fills the task panel at any width, sharply.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._svg = None
        self._aspect = 0.5
        self.setMinimumWidth(160)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)

    def set_svg(self, svg_text):
        from PySide import QtSvg
        self._svg = QtCore.QByteArray(svg_text.encode("utf-8"))
        size = QtSvg.QSvgRenderer(self._svg).defaultSize()
        if size.width() > 0:
            self._aspect = size.height() / size.width()
        self._redraw(self.width())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(width * self._aspect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw(event.size().width())

    def _redraw(self, width):
        from PySide import QtGui as _QtGui, QtSvg
        if self._svg is None or width <= 0:
            return
        height = int(width * self._aspect)
        self.setFixedHeight(height)
        app = QtGui.QApplication.instance()
        ratio = app.devicePixelRatio() if app is not None and hasattr(app, "devicePixelRatio") else 1.0
        pixmap = _QtGui.QPixmap(int(width * ratio), int(height * ratio))
        pixmap.fill(QtCore.Qt.transparent)
        painter = _QtGui.QPainter(pixmap)
        QtSvg.QSvgRenderer(self._svg).render(painter, QtCore.QRectF(0, 0, width * ratio, height * ratio))
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        self.setPixmap(pixmap)


def selection_z(selection, end):
    """
    The Z named by a selection (one feature, or one whole object): a
    vertex's Z; otherwise the feature's front for the front of the Z range
    (end == "front") and its back for the back. A flat face square to the
    axis or a circular edge has one Z; a cylindrical or conical face, or a
    whole object, gives its front or back end. None for anything else.
    """
    if len(selection) != 1:
        return None
    subs = selection[0].SubObjects
    if len(subs) > 1:
        return None
    shape = subs[0] if subs else getattr(selection[0].Object, "Shape", None)
    if shape is None or shape.isNull():
        return None
    if shape.ShapeType == "Vertex":
        return shape.Point.z
    bb = shape.BoundBox
    return bb.ZMax if end == "front" else bb.ZMin


def selection_diameter(selection, which):
    """
    The diameter named by a selection (one sub-element), measured about the
    spindle axis (Z): a circular edge or a cylindrical face gives its
    diameter; a vertex twice its distance from the axis; a flat face with
    circular edges (e.g. the end of a tube) its inner circle for the minimum
    (which == "min") and its outer circle for the maximum. None otherwise.
    """
    import math
    import Part
    if len(selection) != 1 or len(selection[0].SubObjects) != 1:
        return None
    sub = selection[0].SubObjects[0]
    if sub.ShapeType == "Vertex":
        return 2 * math.hypot(sub.Point.x, sub.Point.y)
    if sub.ShapeType == "Edge" and isinstance(sub.Curve, Part.Circle):
        return 2 * sub.Curve.Radius
    if sub.ShapeType == "Face":
        if isinstance(sub.Surface, Part.Cylinder):
            return 2 * sub.Surface.Radius
        radii = [e.Curve.Radius for e in sub.Edges if isinstance(e.Curve, Part.Circle)]
        if radii:
            return 2 * (min(radii) if which == "min" else max(radii))
    return None


class TaskPanelTurnDiametersPage(PathOpGui.TaskPanelDiametersPage):
    """
    CAM's Diameters page with its arrow buttons working, as on the Depths
    page: they transfer the diameter of the selected feature (a circular
    edge, a cylindrical face, a vertex, or a flat face such as the end of a
    tube, whose inner circle is the minimum and outer circle the maximum),
    and a diagram of what the two limits are, in the style of the Heights
    diagram.
    """

    def cleanupPage(self, obj):
        release_widgets(self)
        super().cleanupPage(obj)

    DIAGRAMS = {"External": "CAM-TurnDiameters-External.svg", "Internal": "CAM-TurnDiameters-Internal.svg"}
    # radial distances that belong with the diameters: (checkbox, switch,
    # property, field, label, tooltip)
    CLEARANCES = (
        ("setRetract", "SetRetract", "Retract", "retract", "Retract",
         "Radial lift-off at the end of each pass, beyond the furthest the tool reached. Unticked: step over x "
         "finish passes outside, 0.5 mm (or a quarter of the hole's radius) when boring, shown greyed out"),
        ("setRadialClearance", "SetRadialClearance", "RadialClearance", "radialClearance", "Radial clearance",
         "Radial distance of the safe position (and radial approaches) from the stock, or from the hole when "
         "boring. Unticked: the Setup Sheet's safe height offset outside, 0.5 mm (or a quarter of the hole's "
         "radius) when boring, shown greyed out"),
    )

    def getForm(self):
        form = super().getForm()
        form.startDepthSet.setToolTip(QtCore.QCoreApplication.translate("PathTurn",
            "Transfer the diameter of the selected feature (a circular edge, cylindrical face, vertex, or the "
            "inner circle of a flat face such as a tube's end) as the minimum diameter"))
        form.finalDepthSet.setToolTip(QtCore.QCoreApplication.translate("PathTurn",
            "Transfer the diameter of the selected feature (a circular edge, cylindrical face, vertex, or the "
            "outer circle of a flat face) as the maximum diameter"))
        self.add_switches(form)
        self.add_clearance_rows(form)
        # The diagram goes in a new row at the bottom of CAM's grid: added, not
        # moved (moving CAM's widgets, or walking its layout items, gave PySide
        # wrappers of the wrong type). No container of our own either: one
        # that carried CAM's widgets by name kept their wrappers alive after
        # the panel closed, and PySide then handed one out, dead and of the
        # wrong type, for a new widget at the same address.
        diagram = self.make_diagram()
        layout = form.layout()
        if diagram is not None and layout is not None:
            if hasattr(layout, "rowCount"):
                layout.addWidget(diagram, layout.rowCount(), 0, 1, max(1, layout.columnCount()))
            else:
                layout.addWidget(diagram)
        if layout is not None and hasattr(layout, "setRowStretch"):
            # spare height to an empty last row, not to CAM's spacer between
            # its fields and ours (rows with a stretch factor take it first)
            layout.setRowStretch(layout.rowCount(), 1)
        return form

    def _shows(self, obj, prop):
        '''Retract only for operations made of passes; neither for Turn Thread
        (it has its own clearances).'''
        proxy = getattr(obj, "Proxy", None)
        if not hasattr(obj, prop) or getattr(proxy, "uses_threading_tool", False):
            return False
        return prop != "Retract" or getattr(proxy, "uses_pass_retract", False)

    def add_clearance_rows(self, form):
        layout = form.layout()
        if layout is None or not hasattr(layout, "rowCount"):
            return
        loader = FreeCADGui.UiLoader()
        for box, _, prop, field, text, tip in self.CLEARANCES:
            check = QtGui.QCheckBox(QtCore.QCoreApplication.translate("PathTurn", text))
            check.setObjectName(box)
            check.setToolTip(QtCore.QCoreApplication.translate("PathTurn", tip))
            spin = loader.createWidget("Gui::QuantitySpinBox")
            spin.setObjectName(field)
            spin.setToolTip(check.toolTip())
            spin.setProperty("minimum", 0.0)
            row = layout.rowCount()
            layout.addWidget(check, row, 0)
            layout.addWidget(spin, row, 1)
            setattr(form, box, check)
            setattr(form, field, spin)
            shown = self._shows(self.obj, prop)
            check.setVisible(shown)
            spin.setVisible(shown)

    def _clearance_boxes(self, obj):
        if getattr(self, "_cl_boxes", None) is None:
            if not hasattr(self.form, "retract"):
                return {}
            self._cl_boxes = {prop: PathGuiUtil.QuantitySpinBox(getattr(self.form, field), obj, prop)
                              for _, _, prop, field, _, _ in self.CLEARANCES if hasattr(obj, prop)}
        return self._cl_boxes

    def _clearances(self, obj):
        return [(getattr(self.form, box), switch, prop, getattr(self.form, field))
                for box, switch, prop, field, _, _ in self.CLEARANCES if hasattr(obj, switch)]

    # (checkbox, switch property, value property, the field, CAM's label)
    SWITCHES = (("setMinDiameter", "SetMinDiameter", "MinDiameter", "minDiameter", "startDepthLabel"),
                ("setMaxDiameter", "SetMaxDiameter", "MaxDiameter", "maxDiameter", "finalDepthLabel"))

    def add_switches(self, form):
        '''Each diameter's label becomes a checkbox: unticked, the op works the
        value out (greyed, showing what it uses); ticked, it uses the value.'''
        layout = form.layout()
        tips = {"setMinDiameter": QtCore.QCoreApplication.translate("PathTurn",
                    "Set Min Diameter by hand: Rough, Profile and Turn Groove turn to it across the Z range "
                    "(into the model where it is bigger, left at it where smaller); Face and Partoff stop at it "
                    "(e.g. a bore). Unticked: no inner limit, the op follows the part"),
                "setMaxDiameter": QtCore.QCoreApplication.translate("PathTurn",
                    "Set Max Diameter by hand: where the material starts (e.g. a surface already turned "
                    "smaller). Unticked: the stock's diameter")}
        for box, _, _, _, label in self.SWITCHES:
            old = getattr(form, label, None)
            if old is None or layout is None or not hasattr(layout, "getItemPosition"):
                continue
            check = QtGui.QCheckBox(old.text())
            check.setObjectName(box)
            check.setToolTip(tips[box])
            index = layout.indexOf(old)
            row, col, rows, cols = layout.getItemPosition(index)
            old.hide()
            layout.addWidget(check, row, col, rows, cols)
            setattr(form, box, check)

    def _switched(self, obj):
        return [(getattr(self.form, box, None), switch, prop, getattr(self.form, field))
                for box, switch, prop, field, _ in self.SWITCHES if hasattr(obj, switch)]

    def getFields(self, obj):
        for check, switch, prop, field in self._switched(obj):
            if check is not None and getattr(obj, switch) != check.isChecked():
                setattr(obj, switch, check.isChecked())
        # only values set by hand are written; the rest the op works out
        if getattr(obj, "SetMinDiameter", True):
            self.minDiameter.updateProperty()
        if getattr(obj, "SetMaxDiameter", True):
            self.maxDiameter.updateProperty()
        boxes = self._clearance_boxes(obj)
        for check, switch, prop, _ in self._clearances(obj):
            if getattr(obj, switch) != check.isChecked():
                setattr(obj, switch, check.isChecked())
            if getattr(obj, switch) and prop in boxes:
                boxes[prop].updateProperty()

    def setFields(self, obj):
        super().setFields(obj)
        self.show_diagram(obj)
        for box in self._clearance_boxes(obj).values():
            box.updateWidget()
        for check, switch, prop, field in self._clearances(obj):
            check.blockSignals(True)
            check.setChecked(bool(getattr(obj, switch)))
            check.blockSignals(False)
            field.setEnabled(bool(getattr(obj, switch)))
        for check, switch, prop, field in self._switched(obj):
            if check is None:
                continue
            check.blockSignals(True)
            check.setChecked(bool(getattr(obj, switch)))
            check.blockSignals(False)
            field.setEnabled(bool(getattr(obj, switch)))

    def getSignalsForUpdate(self, obj):
        signals = super().getSignalsForUpdate(obj)
        for check, _, _, _ in self._switched(obj):
            if check is not None:
                signals.append(check.stateChanged)
        for check, _, _, field in self._clearances(obj):
            signals.append(check.stateChanged)
            signals.append(field.editingFinished)
        return signals

    def pageUpdateData(self, obj, prop):
        # what the op works out (greyed fields) follows the op; a value set by
        # hand is being edited here, so it is left alone
        if prop == "Side":
            self.show_diagram(obj)
        if prop in ("Retract", "RadialClearance", "SetRetract", "SetRadialClearance"):
            boxes = self._clearance_boxes(obj)
            for check, switch, value, field in self._clearances(obj):
                if not getattr(obj, switch) and value in boxes:
                    boxes[value].updateWidget()
                check.blockSignals(True)
                check.setChecked(bool(getattr(obj, switch)))
                check.blockSignals(False)
                field.setEnabled(bool(getattr(obj, switch)))
        if prop in ("MinDiameter", "MaxDiameter", "SetMinDiameter", "SetMaxDiameter"):
            for check, switch, value, field in self._switched(obj):
                if not getattr(obj, switch):
                    (self.minDiameter if value == "MinDiameter" else self.maxDiameter).updateWidget()
                if check is not None:
                    check.blockSignals(True)
                    check.setChecked(bool(getattr(obj, switch)))
                    check.blockSignals(False)
                    field.setEnabled(bool(getattr(obj, switch)))

    # the diagrams' placeholder colours, swapped for the theme: dark labels and
    # lines on a light theme, near-white ones and a stronger band on a dark one
    THEMES = {
        False: {"#8a8a8a": "#2e2e2e", "#999999": "#5c5c5c", "#c6ae4f": "#9c7d14",
                "fill-opacity:0.35": "fill-opacity:0.40"},
        True: {"#8a8a8a": "#f0f0f0", "#999999": "#cfcfcf", "#c6ae4f": "#f0d060",
               "fill-opacity:0.35": "fill-opacity:0.55"},
    }

    def _diagram_svg(self, side):
        '''The side's diagram as SVG text, coloured for the theme.'''
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "Gui", "Resources", "Icons", self.DIAGRAMS.get(side, self.DIAGRAMS["External"]))
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fp:
            text = fp.read()
        app = QtGui.QApplication.instance()
        dark = app is not None and app.palette().color(QtGui.QPalette.Window).lightness() < 128
        for a, b in self.THEMES[dark].items():
            text = text.replace(a, b)
        return text

    def show_diagram(self, obj):
        '''The diagram for the operation's side (boring has its own).'''
        label = getattr(self, "_diagram", None)
        side = getattr(obj, "Side", "External")
        if label is not None and getattr(self, "_diagram_side", None) != side:
            text = self._diagram_svg(side)
            if text is not None:
                label.set_svg(text)
                self._diagram_side = side

    def make_diagram(self):
        '''The diagram for the op's side, as a widget for above the form.'''
        side = getattr(getattr(self, "obj", None), "Side", "External")
        text = self._diagram_svg(side)
        if text is None:
            return None
        label = SvgDiagram()
        label.set_svg(text)
        label.setObjectName("diametersDiagram")
        self._diagram, self._diagram_side = label, side
        return label

    def registerSignalHandlers(self, obj):
        self.form.startDepthSet.clicked.connect(lambda: self.diameterSet(obj, self.minDiameter, "MinDiameter", "min"))
        self.form.finalDepthSet.clicked.connect(lambda: self.diameterSet(obj, self.maxDiameter, "MaxDiameter", "max"))
        for check, _, _, field in self._switched(obj):
            if check is not None:
                check.toggled.connect(field.setEnabled)
        for check, _, _, field in self._clearances(obj):
            check.toggled.connect(field.setEnabled)

    def diameterSet(self, obj, spinbox, prop, which):
        d = selection_diameter(FreeCADGui.Selection.getSelectionEx(), which)
        if d is None:
            return
        # a diameter taken from the model is set by hand: tick it
        switch = "SetMinDiameter" if prop == "MinDiameter" else "SetMaxDiameter"
        check = getattr(self.form, "setMinDiameter" if prop == "MinDiameter" else "setMaxDiameter", None)
        if hasattr(obj, switch) and not getattr(obj, switch):
            setattr(obj, switch, True)
            self.setDirty()
        if check is not None:
            check.blockSignals(True)
            check.setChecked(True)
            check.blockSignals(False)
            spinbox.widget.setEnabled(True)
        if spinbox.expression():
            obj.setExpression(prop, None)
            self.setDirty()
        spinbox.updateWidget(FreeCAD.Units.Quantity(d, FreeCAD.Units.Length))
        if spinbox.updateProperty():
            self.setDirty()

    def updateSelection(self, obj, sel):
        self.form.startDepthSet.setEnabled(selection_diameter(sel, "min") is not None)
        self.form.finalDepthSet.setEnabled(selection_diameter(sel, "max") is not None)


def imperial_units():
    '''True when lengths show in inches: surface speed then in ft/min, as
    CAM's Feeds & Speeds tab shows it.'''
    try:
        unit = FreeCAD.Units.Quantity(1.0, "mm").getUserPreferred()[2]
    except Exception:
        return False
    return any(token in unit for token in ("in", "ft", "thou", '"', "'"))


M_MIN_PER_FT_MIN = 0.3048


class TaskPanelTurnBase(PathOpGui.TaskPanelPage):

    def cleanupPage(self, obj):
        release_widgets(self)
        super().cleanupPage(obj)
    # The tool controller and coolant are on CAM's own Tool Controller page;
    # these pages used to carry them too, and setting them up twice made CAM
    # delete widgets out from under this page.
    '''Page controller class for turning operations '''

    def taskPanelDiametersPage(self, obj, features):
        '''The Diameters page with its from-selection buttons working.'''
        return TaskPanelTurnDiametersPage(obj, features)

    def taskPanelDiametersPage(self, obj, features):
        '''The Diameters page, with its from-selection buttons and diagram.'''
        return TaskPanelTurnDiametersPage(obj, features)

    def taskPanelBaseGeometryPage(self, obj, features):
        '''Use the Base Geometry page with the turning note.'''
        return TaskPanelTurnBaseGeometryPage(obj, features)

    def initPage(self, obj):
        self.updating = False  # pylint: disable=attribute-defined-outside-init

    def getForm(self):
        '''getForm() ... return UI'''
        # return FreeCADGui.PySideUic.loadUi(":/panels/PageOpTurnBaseEdit.ui")
        turnUi = PathTurnHelpers.getResourcePath("PageOpTurnBaseEdit.ui")
        return FreeCADGui.PySideUic.loadUi(turnUi)

    # length fields, as CAM's own op pages do them: Gui::QuantitySpinBox bound
    # to the property (units, styling, and the fx button for expressions)
    QUANTITY_FIELDS = (("stepOver", "StepOver"), ("stockToLeaveX", "StockToLeaveX"), ("stockToLeaveZ", "StockToLeaveZ"),
                       ("finishStepOver", "FinishStepOver"))
    def _lead_in_box(self, obj):
        if getattr(self, "_lead_box", None) is None and hasattr(obj, "LeadIn"):
            self._lead_box = PathGuiUtil.QuantitySpinBox(self.form.leadIn, obj, "LeadIn")
        return getattr(self, "_lead_box", None)

    def updateData(self, obj, prop):
        '''The worked-out (greyed) lead-in and step down follow the op as it recomputes.'''
        if prop in ("SurfaceSpeed", "SurfaceSpeedSource", "MaxSpindleSpeed") and hasattr(self, "form"):
            self._css_values(obj)
        if prop == "LeadIn" and hasattr(self, "form") and not getattr(obj, "SetLeadIn", True):
            box = self._lead_in_box(obj)
            if box is not None:
                box.updateWidget()
        if prop == "StepDown" and hasattr(self, "form") and not getattr(obj, "SetStepDown", True):
            box = self._groove_boxes(obj).get("StepDown")
            if box is not None:
                box.updateWidget()

    def _groove_boxes(self, obj):
        '''Step down, the pecking lengths, the edge break and corner sizes, bound to the op.'''
        if getattr(self, "_gboxes", None) is None:
            self._gboxes = {prop: PathGuiUtil.QuantitySpinBox(getattr(self.form, field), obj, prop)
                            for field, prop in (("stepDown", "StepDown"), ("peckDepth", "PeckDepth"),
                                                ("peckRetract", "PeckRetract"), ("breakEdgeSize", "BreakEdgeSize"),
                                                ("cornerSize", "CornerSize")) if hasattr(obj, prop)}
        return self._gboxes

    def registerSignalHandlers(self, obj):
        self.form.setLeadIn.toggled.connect(self.form.leadIn.setEnabled)
        self.form.setStepDown.toggled.connect(self.form.stepDown.setEnabled)
        for w in (self.form.peckDepth, self.form.peckRetract, self.form.peckFullRetract, self.form.label_peckRetract):
            self.form.peck.toggled.connect(w.setEnabled)
        self.form.strategy.currentIndexChanged.connect(lambda _: self._side_turn_fields())
        self.form.breakEdges.toggled.connect(self.form.breakEdgeSize.setEnabled)
        for w in (self.form.css, self.form.setSurfaceSpeed, self.form.setMaxSpindleSpeed):
            w.toggled.connect(lambda _: self._css_enabled())

    def _side_turn_fields(self):
        on = self.form.strategy.currentText() == "Side-turn"
        self.form.setStepDown.setEnabled(on)
        self.form.stepDown.setEnabled(on and self.form.setStepDown.isChecked())

    def _css_enabled(self):
        on = self.form.css.isChecked()
        for switch, field in ((self.form.setSurfaceSpeed, self.form.surfaceSpeed),
                              (self.form.setMaxSpindleSpeed, self.form.maxSpindleSpeed)):
            switch.setEnabled(on)
            field.setEnabled(on and switch.isChecked())
        self.form.surfaceSpeedSource.setEnabled(on)

    def _css_values(self, obj):
        '''The surface speed (m/min, or ft/min in inches), where it came from,
        and the maximum spindle speed, into the fields.'''
        if not hasattr(obj, "ConstantSurfaceSpeed"):
            return
        imperial = imperial_units()
        self.form.surfaceSpeed.blockSignals(True)
        self.form.surfaceSpeed.setSuffix(" ft/min" if imperial else " m/min")
        self.form.surfaceSpeed.setValue(obj.SurfaceSpeed / (M_MIN_PER_FT_MIN if imperial else 1.0))
        self.form.surfaceSpeed.blockSignals(False)
        source = obj.SurfaceSpeedSource or ""
        self.form.surfaceSpeedSource.setText(FreeCAD.Qt.translate("PathTurn", "From: {}").format(source) if source else "")
        self.form.maxSpindleSpeed.blockSignals(True)
        self.form.maxSpindleSpeed.setValue(int(round(obj.MaxSpindleSpeed)))
        self.form.maxSpindleSpeed.blockSignals(False)

    def _css_fields(self, obj):
        for widget, prop in ((self.form.css, "ConstantSurfaceSpeed"), (self.form.setSurfaceSpeed, "SetSurfaceSpeed"),
                             (self.form.setMaxSpindleSpeed, "SetMaxSpindleSpeed")):
            widget.blockSignals(True)
            widget.setChecked(bool(getattr(obj, prop)))
            widget.blockSignals(False)
        self._css_values(obj)
        self._css_enabled()

    def _get_css_fields(self, obj):
        for widget, prop in ((self.form.css, "ConstantSurfaceSpeed"), (self.form.setSurfaceSpeed, "SetSurfaceSpeed"),
                             (self.form.setMaxSpindleSpeed, "SetMaxSpindleSpeed")):
            if getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())
        # only values set by hand are written; worked-out ones are shown
        if obj.SetSurfaceSpeed:
            value = self.form.surfaceSpeed.value() * (M_MIN_PER_FT_MIN if imperial_units() else 1.0)
            if abs(obj.SurfaceSpeed - value) > 1e-6:
                obj.SurfaceSpeed = value
        if obj.SetMaxSpindleSpeed and abs(obj.MaxSpindleSpeed - self.form.maxSpindleSpeed.value()) > 1e-6:
            obj.MaxSpindleSpeed = float(self.form.maxSpindleSpeed.value())

    def _spinboxes(self, obj):
        if getattr(self, "_quantity_boxes", None) is None:
            self._quantity_boxes = [PathGuiUtil.QuantitySpinBox(getattr(self.form, widget), obj, prop)
                                    for widget, prop in self.QUANTITY_FIELDS if hasattr(obj, prop)]
            FreeCADGui.ExpressionBinding(self.form.finishPasses).bind(obj, "FinishPasses")
        return self._quantity_boxes

    def _show_fields(self, obj):
        '''Show only the fields the operation uses.'''
        has_finish = hasattr(obj, "SpringPass")          # Profile, Turn Groove
        is_profile = hasattr(obj, "FinishFrontFace")
        # Profile's passes are spaced by Finish step over, not Step over
        self.form.stepOver.setVisible(not is_profile)
        self.form.label_4.setVisible(not is_profile)
        for widget in (self.form.finishPasses, self.form.label_5, self.form.springPass):
            widget.setVisible(has_finish)
        for widget in (self.form.finishStepOver, self.form.label_8):
            widget.setVisible(hasattr(obj, "FinishStepOver"))
        self.form.finishFrontFace.setVisible(is_profile)
        for widget in (self.form.finishDirection, self.form.label_9b):
            widget.setVisible(hasattr(obj, "FinishDirection"))
        for widget in (self.form.side, self.form.label_side):
            widget.setVisible(hasattr(obj, "Side"))
        for widget in (self.form.setLeadIn, self.form.leadIn):
            widget.setVisible(hasattr(obj, "LeadIn") and getattr(getattr(obj, "Proxy", None), "uses_pass_lead_in", False))
        for widget in (self.form.label_strategy, self.form.strategy, self.form.setStepDown, self.form.stepDown):
            widget.setVisible(hasattr(obj, "Strategy"))
        for widget in (self.form.peck, self.form.peckDepth, self.form.label_peckRetract, self.form.peckRetract,
                       self.form.peckFullRetract):
            widget.setVisible(hasattr(obj, "Peck"))
        for widget in (self.form.breakEdges, self.form.breakEdgeSize):
            widget.setVisible(hasattr(obj, "BreakEdges"))
        for widget in (self.form.label_cornerType, self.form.cornerType, self.form.label_cornerSize, self.form.cornerSize):
            widget.setVisible(hasattr(obj, "CornerType"))
        for widget in (self.form.css, self.form.setSurfaceSpeed, self.form.surfaceSpeed, self.form.surfaceSpeedSource,
                       self.form.setMaxSpindleSpeed, self.form.maxSpindleSpeed):
            widget.setVisible(hasattr(obj, "ConstantSurfaceSpeed"))
        if hasattr(obj, "CornerType"):
            # one pass per corner: no step over
            for name in ("stepOver", "label_4"):
                widget = getattr(self.form, name, None)
                if widget is not None:
                    widget.setVisible(False)

    def getFields(self, obj):
        '''getFields(obj) ... transfers values from UI to obj's proprties'''
        PathLog.track()

        for box in self._spinboxes(obj):
            box.updateProperty()

        if obj.FinishPasses != self.form.finishPasses.value():
            obj.FinishPasses = self.form.finishPasses.value()

        if hasattr(obj, "SpringPass") and obj.SpringPass != self.form.springPass.isChecked():
            obj.SpringPass = self.form.springPass.isChecked()

        if hasattr(obj, "FinishFrontFace") and obj.FinishFrontFace != self.form.finishFrontFace.isChecked():
            obj.FinishFrontFace = self.form.finishFrontFace.isChecked()

        if hasattr(obj, "FinishDirection") and obj.FinishDirection != self.form.finishDirection.currentText():
            obj.FinishDirection = self.form.finishDirection.currentText()

        if hasattr(obj, "Side") and self.form.side.currentText() and obj.Side != self.form.side.currentText():
            obj.Side = self.form.side.currentText()

        if obj.AllowGrooving != self.form.allowGrooving.isChecked():
            obj.AllowGrooving = self.form.allowGrooving.isChecked()

        if hasattr(obj, "Strategy") and self.form.strategy.currentText() and obj.Strategy != self.form.strategy.currentText():
            obj.Strategy = self.form.strategy.currentText()
        if hasattr(obj, "SetStepDown") and obj.SetStepDown != self.form.setStepDown.isChecked():
            obj.SetStepDown = self.form.setStepDown.isChecked()
        for widget, prop in ((self.form.peck, "Peck"), (self.form.peckFullRetract, "PeckFullRetract"),
                             (self.form.breakEdges, "BreakEdges")):
            if hasattr(obj, prop) and getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())
        if hasattr(obj, "CornerType") and self.form.cornerType.currentText() and obj.CornerType != self.form.cornerType.currentText():
            obj.CornerType = self.form.cornerType.currentText()
        for prop, box in self._groove_boxes(obj).items():
            if prop != "StepDown" or getattr(obj, "SetStepDown", False):    # a worked-out step down is shown, not written
                box.updateProperty()

        if hasattr(obj, "ConstantSurfaceSpeed"):
            self._get_css_fields(obj)

        if hasattr(obj, "SetLeadIn"):
            if obj.SetLeadIn != self.form.setLeadIn.isChecked():
                obj.SetLeadIn = self.form.setLeadIn.isChecked()
            if obj.SetLeadIn and self._lead_in_box(obj) is not None:
                self._lead_in_box(obj).updateProperty()    # only a value set by hand is written


    def setFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        PathLog.track()

        for box in self._spinboxes(obj):
            box.updateWidget()
        self.form.finishPasses.setValue(obj.FinishPasses)

        self._show_fields(obj)
        if hasattr(obj, "Strategy"):
            self.form.strategy.blockSignals(True)
            self.form.strategy.clear()
            self.form.strategy.addItems(obj.getEnumerationsOfProperty("Strategy"))
            self.form.strategy.setCurrentText(obj.Strategy)
            self.form.strategy.blockSignals(False)
            self.form.setStepDown.blockSignals(True)
            self.form.setStepDown.setChecked(bool(obj.SetStepDown))
            self.form.setStepDown.blockSignals(False)
            self._side_turn_fields()
        if hasattr(obj, "Peck"):
            for widget, prop in ((self.form.peck, "Peck"), (self.form.peckFullRetract, "PeckFullRetract")):
                widget.blockSignals(True)
                widget.setChecked(bool(getattr(obj, prop)))
                widget.blockSignals(False)
            for w in (self.form.peckDepth, self.form.peckRetract, self.form.peckFullRetract, self.form.label_peckRetract):
                w.setEnabled(bool(obj.Peck))
        if hasattr(obj, "BreakEdges"):
            self.form.breakEdges.blockSignals(True)
            self.form.breakEdges.setChecked(bool(obj.BreakEdges))
            self.form.breakEdges.blockSignals(False)
            self.form.breakEdgeSize.setEnabled(bool(obj.BreakEdges))
        if hasattr(obj, "CornerType"):
            self.form.cornerType.blockSignals(True)
            self.form.cornerType.clear()
            self.form.cornerType.addItems(obj.getEnumerationsOfProperty("CornerType"))
            self.form.cornerType.setCurrentText(obj.CornerType)
            self.form.cornerType.blockSignals(False)
        for box in self._groove_boxes(obj).values():
            box.updateWidget()
        if hasattr(obj, "SetLeadIn"):
            self.form.setLeadIn.blockSignals(True)
            self.form.setLeadIn.setChecked(bool(obj.SetLeadIn))
            self.form.setLeadIn.blockSignals(False)
            self.form.leadIn.setEnabled(bool(obj.SetLeadIn))
            if self._lead_in_box(obj) is not None:
                self._lead_in_box(obj).updateWidget()
        if hasattr(obj, "SpringPass"):
            self.form.springPass.setChecked(obj.SpringPass)
        if hasattr(obj, "FinishFrontFace"):
            self.form.finishFrontFace.setChecked(obj.FinishFrontFace)
        if hasattr(obj, "FinishDirection"):
            self.form.finishDirection.blockSignals(True)
            self.form.finishDirection.clear()
            self.form.finishDirection.addItems(obj.getEnumerationsOfProperty("FinishDirection"))
            self.form.finishDirection.setCurrentText(obj.FinishDirection)
            self.form.finishDirection.blockSignals(False)
        if hasattr(obj, "Side"):
            self.form.side.blockSignals(True)
            self.form.side.clear()
            self.form.side.addItems(obj.getEnumerationsOfProperty("Side"))
            self.form.side.setCurrentText(obj.Side)
            self.form.side.blockSignals(False)

        if hasattr(obj, "ConstantSurfaceSpeed"):
            self._css_fields(obj)

        if obj.AllowGrooving:
            self.form.allowGrooving.setCheckState(QtCore.Qt.Checked)
        else:
            self.form.allowGrooving.setCheckState(QtCore.Qt.Unchecked)

        self.setOpFields(obj)

    def getSignalsForUpdate(self, obj):
        '''getSignalsForUpdate(obj) ... return list of signals for updating obj'''
        signals = []

        signals.append(self.form.stepOver.editingFinished)
        signals.append(self.form.stockToLeaveX.editingFinished)
        signals.append(self.form.stockToLeaveZ.editingFinished)
        signals.append(self.form.finishPasses.valueChanged)
        signals.append(self.form.side.currentIndexChanged)
        signals.append(self.form.setLeadIn.stateChanged)
        signals.append(self.form.leadIn.editingFinished)
        signals += [self.form.strategy.currentIndexChanged, self.form.setStepDown.stateChanged,
                    self.form.stepDown.editingFinished, self.form.peck.stateChanged, self.form.peckDepth.editingFinished,
                    self.form.peckRetract.editingFinished, self.form.peckFullRetract.stateChanged,
                    self.form.breakEdges.stateChanged, self.form.breakEdgeSize.editingFinished,
                    self.form.cornerType.currentIndexChanged, self.form.cornerSize.editingFinished]
        signals.append(self.form.springPass.stateChanged)
        signals.append(self.form.finishStepOver.editingFinished)
        signals.append(self.form.finishFrontFace.stateChanged)
        signals.append(self.form.finishDirection.currentIndexChanged)
        signals.append(self.form.allowGrooving.stateChanged)
        signals += [self.form.css.stateChanged, self.form.setSurfaceSpeed.stateChanged,
                    self.form.surfaceSpeed.editingFinished, self.form.setMaxSpindleSpeed.stateChanged,
                    self.form.maxSpindleSpeed.editingFinished]


        return signals

    def setOpFields(self, obj):
        '''setOpFields(obj) ... overwrite to set operations specific values.
        Should be overwritten by subclasses.'''
        pass  # pylint: disable=unnecessary-pass
