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

TURNING_OPS = ("TurnFace", "TurnProfile", "TurnPartoff", "TurnRough", "TurnGroove")


class TurningGate:
    """Allow faces, edges and whole objects with a shape; not vertices."""

    def allow(self, doc, obj, sub):
        if not hasattr(obj, "Shape"):
            return False
        if not sub:
            return True
        return sub.startswith("Face") or sub.startswith("Edge")


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

    NOTE = QtCore.QT_TRANSLATE_NOOP(
        "PathTurn",
        "Turning uses the selection only for its position along the Z axis: the "
        "operation is limited to the Z range from the front-most to the back-most "
        "selected face, edge or object (e.g. a sketch or wire), and everything in that "
        "range is turned, including geometry between them that is not selected. This "
        "sets Start Depth and Final Depth. With nothing selected, the operation covers "
        "the whole stock.")

    def getTitle(self, obj):
        return FreeCAD.Qt.translate("PathTurn", "Z Range")

    def modifyPanel(self, panel):
        super().modifyPanel(panel)
        label = QtGui.QLabel(FreeCAD.Qt.translate("PathTurn", self.NOTE))
        label.setWordWrap(True)
        label.setObjectName("turningBaseGeometryNote")
        # the resulting front and back, updated whenever the list changes
        self.rangeLabel = QtGui.QLabel()
        self.rangeLabel.setWordWrap(True)
        self.rangeLabel.setObjectName("turningBaseGeometryRange")
        layout = panel.layout()
        if layout is None:
            return
        if hasattr(layout, "insertWidget"):
            # box layout: put the note and the range first
            layout.insertWidget(0, label)
            layout.insertWidget(1, self.rangeLabel)
        else:
            # grid layout: add them below the existing widgets, full width
            columns = max(1, layout.columnCount())
            layout.addWidget(label, layout.rowCount(), 0, 1, columns)
            layout.addWidget(self.rangeLabel, layout.rowCount(), 0, 1, columns)

    def rangeText(self):
        '''The front and back of the selection, and which faces set them.'''
        front = back = None
        for base_obj, subs in (self.obj.Base or []):
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
        if front is None:
            return FreeCAD.Qt.translate("PathTurn", "Nothing selected: the whole stock.")

        def z(value):
            return FreeCAD.Units.Quantity(value, FreeCAD.Units.Length).UserString

        text = FreeCAD.Qt.translate("PathTurn", "Front: Z {} ({})    Back: Z {} ({})").format(
            z(front[0]), front[1], z(back[0]), back[1])
        if front[0] - back[0] <= 1e-4:
            text += "\n" + FreeCAD.Qt.translate(
                "PathTurn",
                "The selection has no length along Z: select geometry at two different Z positions.")
        return text

    def updateRangeLabel(self):
        label = getattr(self, "rangeLabel", None)
        if label is not None:
            label.setText(self.rangeText())

    # the list is refreshed through these; update the range after each
    def setFields(self, obj):
        super().setFields(obj)
        self.updateRangeLabel()

    def updateBase(self):
        super().updateBase()
        self.updateRangeLabel()

    def clearBase(self):
        super().clearBase()
        self.updateRangeLabel()


class TaskPanelTurnBase(PathOpGui.TaskPanelPage):
    '''Page controller class for turning operations '''

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

        if obj.AllowGrooving != self.form.allowGrooving.isChecked():
            obj.AllowGrooving = self.form.allowGrooving.isChecked()

        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

    def setFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        PathLog.track()

        for box in self._spinboxes(obj):
            box.updateWidget()
        self.form.finishPasses.setValue(obj.FinishPasses)
        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

        self._show_fields(obj)
        if hasattr(obj, "SpringPass"):
            self.form.springPass.setChecked(obj.SpringPass)
        if hasattr(obj, "FinishFrontFace"):
            self.form.finishFrontFace.setChecked(obj.FinishFrontFace)

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
        signals.append(self.form.springPass.stateChanged)
        signals.append(self.form.finishStepOver.editingFinished)
        signals.append(self.form.finishFrontFace.stateChanged)
        signals.append(self.form.allowGrooving.stateChanged)

        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)

        return signals

    def setOpFields(self, obj):
        '''setOpFields(obj) ... overwrite to set operations specific values.
        Should be overwritten by subclasses.'''
        pass  # pylint: disable=unnecessary-pass
