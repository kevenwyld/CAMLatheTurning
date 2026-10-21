# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Thread operation."""

import FreeCAD
import FreeCADGui
import Path.Base.Gui.Util as PathGuiUtil
import Path.Op.Gui.Base as PathOpGui
import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnThread as PathTurnThread

from PySide import QtCore

COMBOS = (("threadStandard", "ThreadStandard"), ("threadSize", "ThreadSize"), ("threadType", "ThreadType"),
          ("infeed", "Infeed"))
QUANTITIES = (("pitch", "Pitch"), ("threadDepth", "ThreadDepth"), ("threadLength", "ThreadLength"),
              ("firstPassDepth", "FirstPassDepth"), ("minPassDepth", "MinPassDepth"), ("leadIn", "LeadIn"))
INTEGERS = (("passes", "Passes"), ("springPasses", "SpringPasses"))


class TaskPanelOpPage(PathTurnBaseGui.TaskPanelTurnBase):
    '''Page controller for the Turn Thread operation: its own form.'''

    def getForm(self):
        return FreeCADGui.PySideUic.loadUi(PathTurnHelpers.getResourcePath("PageOpTurnThreadEdit.ui"))

    def _spinboxes(self, obj):
        if getattr(self, "_quantity_boxes", None) is None:
            self._quantity_boxes = [PathGuiUtil.QuantitySpinBox(getattr(self.form, w), obj, p) for w, p in QUANTITIES]
            for w, p in INTEGERS:
                FreeCADGui.ExpressionBinding(getattr(self.form, w)).bind(obj, p)
        return self._quantity_boxes

    def _fill_combo(self, combo, obj, prop):
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(obj.getEnumerationsOfProperty(prop))
        combo.setCurrentText(getattr(obj, prop))
        combo.blockSignals(False)

    def getFields(self, obj):
        # the standard first: changing it changes the sizes on offer
        for widget, prop in COMBOS:
            text = getattr(self.form, widget).currentText()
            if text and getattr(obj, prop) != text and text in obj.getEnumerationsOfProperty(prop):
                setattr(obj, prop, text)
        custom = obj.ThreadStandard == "Custom"
        for box in self._spinboxes(obj):
            # the pitch and depth come from the standard unless Custom
            if box.prop in ("Pitch", "ThreadDepth") and not custom:
                continue
            box.updateProperty()
        for widget, prop in INTEGERS:
            value = getattr(self.form, widget).value()
            if getattr(obj, prop) != value:
                setattr(obj, prop, value)
        if obj.UseG76 != self.form.useG76.isChecked():
            obj.UseG76 = self.form.useG76.isChecked()
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)
        # the sizes, pitch and depth follow the standard; refresh just those
        # (setFields also rebuilds the tool controller editor, which CAM
        # expects once, when the page opens)
        self.refresh_thread_fields(obj)

    def setFields(self, obj):
        self.refresh_thread_fields(obj)
        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

    def refresh_thread_fields(self, obj):
        for widget, prop in COMBOS:
            self._fill_combo(getattr(self.form, widget), obj, prop)
        for box in self._spinboxes(obj):
            box.updateWidget()
        for widget, prop in INTEGERS:
            getattr(self.form, widget).setValue(getattr(obj, prop))
        self.form.useG76.setChecked(obj.UseG76)
        custom = obj.ThreadStandard == "Custom"
        self.form.pitch.setEnabled(custom)
        self.form.threadDepth.setEnabled(custom)
        self.form.threadSize.setEnabled(not custom)
        if obj.ThreadDiameter.Value > 0:
            self.form.threadInfo.setText(
                "Cut from the selected face: {} diameter".format(obj.ThreadDiameter.UserString))
        else:
            self.form.threadInfo.setText("Select the cylindrical face to thread on the Z Range page.")

    def getSignalsForUpdate(self, obj):
        signals = [self.form.toolController.currentIndexChanged, self.form.coolantController.currentIndexChanged,
                   self.form.useG76.stateChanged]
        signals += [getattr(self.form, w).currentIndexChanged for w, _ in COMBOS]
        signals += [getattr(self.form, w).editingFinished for w, _ in QUANTITIES]
        signals += [getattr(self.form, w).valueChanged for w, _ in INTEGERS]
        return signals


Command = PathOpGui.SetupOperation('TurnThread',
                                   PathTurnThread.Create,
                                   TaskPanelOpPage,
                                   'CAM-TurnThread',
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnThread", "Turn Thread"),
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnThread",
                                                            "Cuts a single-point thread on the selected cylindrical "
                                                            "face with a threading insert"),
                                   PathTurnThread.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathTurnThreadGui... done\n")
