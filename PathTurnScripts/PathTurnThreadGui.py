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
          ("toleranceClass", "ToleranceClass"), ("infeed", "Infeed"))
QUANTITIES = (("pitch", "Pitch"), ("threadDepth", "ThreadDepth"), ("threadLength", "ThreadLength"),
              ("firstPassDepth", "FirstPassDepth"), ("minPassDepth", "MinPassDepth"), ("leadIn", "LeadIn"),
              ("runOut", "RunOut"))
INTEGERS = (("passes", "Passes"), ("springPasses", "SpringPasses"))
# a checkbox that sets a value by hand: (checkbox, switch property, value widget)
SWITCHES = (("setThreadLength", "SetThreadLength", "threadLength"), ("setPasses", "SetPasses", "passes"),
            ("setFirstPassDepth", "SetFirstPassDepth", "firstPassDepth"), ("setLeadIn", "SetLeadIn", "leadIn"),
            ("setRunOut", "SetRunOut", "runOut"))
VALUE_OF = {"threadLength": "ThreadLength", "passes": "Passes", "firstPassDepth": "FirstPassDepth", "leadIn": "LeadIn", "runOut": "RunOut"}


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

    @staticmethod
    def _auto(obj, prop):
        '''True when the op works prop out (its Set switch is off).'''
        for _, switch, widget in SWITCHES:
            if VALUE_OF.get(widget) == prop:
                return not getattr(obj, switch)
        return False

    def getFields(self, obj):
        # the standard first: changing it changes the sizes on offer
        for widget, prop in COMBOS:
            text = getattr(self.form, widget).currentText()
            if text and getattr(obj, prop) != text and text in obj.getEnumerationsOfProperty(prop):
                setattr(obj, prop, text)
        # the Set switches before the values
        # (unchecked first, so Passes and First pass depth never both end up set)
        for box, switch, _ in sorted(SWITCHES, key=lambda s: getattr(self.form, s[0]).isChecked()):
            checked = getattr(self.form, box).isChecked()
            if getattr(obj, switch) != checked:
                setattr(obj, switch, checked)
        custom = obj.ThreadStandard == "Custom"
        for box in self._spinboxes(obj):
            # the pitch and depth come from the standard unless Custom; values
            # the op works out are shown, not written
            if (box.prop in ("Pitch", "ThreadDepth") and not custom) or self._auto(obj, box.prop):
                continue
            box.updateProperty()
        for widget, prop in INTEGERS:
            if self._auto(obj, prop):
                continue
            value = getattr(self.form, widget).value()
            if getattr(obj, prop) != value:
                setattr(obj, prop, value)
        if obj.UseG76 != self.form.useG76.isChecked():
            obj.UseG76 = self.form.useG76.isChecked()
        if abs(obj.Degression - self.form.degression.value()) > 1e-9:
            obj.Degression = self.form.degression.value()
        # the sizes, pitch and depth follow the standard
        self.refresh_thread_fields(obj)

    def setFields(self, obj):
        self.refresh_checks(obj)
        self.refresh_thread_fields(obj)

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
        self.form.degression.blockSignals(True)
        self.form.degression.setValue(obj.Degression)
        self.form.degression.blockSignals(False)
        for box, switch, widget in SWITCHES:
            checkbox = getattr(self.form, box)
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(getattr(obj, switch)))
            checkbox.blockSignals(False)
            getattr(self.form, widget).setEnabled(bool(getattr(obj, switch)))
        self.refresh_results(obj)

    # properties the op works out when it recomputes, shown on the page
    RESULTS = ("Pitch", "ThreadDepth", "ThreadDiameter", "PassSchedule", "SizeWarning",
               "ThreadLength", "Passes", "FirstPassDepth", "LeadIn", "RunOut", "ToleranceClass", "ThreadReport")

    def updateData(self, obj, prop):
        '''CAM calls this when a property is assigned: show what the op worked
        out (a new op has no diameter until it first recomputes, after the
        page opened). Only those fields, so values being edited are kept.'''
        if prop in ("LastRefusal", "IgnoredChecks"):
            self.refresh_checks(obj)
        if prop in self.RESULTS and hasattr(self, "form"):
            self.refresh_results(obj)

    def refresh_results(self, obj):
        # what the op works out: the standard's pitch and depth, and the
        # values not set by hand (shown greyed out); values being typed in
        # (set by hand) are left alone
        for box in self._spinboxes(obj):
            if box.prop in ("Pitch", "ThreadDepth") or self._auto(obj, box.prop):
                box.updateWidget()
        for widget, prop in INTEGERS:
            if self._auto(obj, prop):
                spin = getattr(self.form, widget)
                spin.blockSignals(True)
                spin.setValue(getattr(obj, prop))
                spin.blockSignals(False)
        # the classes on offer follow the standard and whether it is internal,
        # which the op knows once the selection is made
        if hasattr(obj, "ToleranceClass"):
            self._fill_combo(self.form.toleranceClass, obj, "ToleranceClass")
        if obj.ThreadDiameter.Value > 0 and not getattr(obj, "ThreadReport", "") and getattr(obj, "SizeWarning", ""):
            self.form.threadInfo.setText("")      # the op could not cut it: the red text says why
        elif obj.ThreadDiameter.Value > 0:
            if getattr(obj, "ThreadReport", ""):
                self.form.threadInfo.setText(obj.ThreadReport)
            else:
                lines = ["Cut from the selected diameter: {}".format(obj.ThreadDiameter.UserString)]
                if getattr(obj, "PassSchedule", ""):
                    lines.append(obj.PassSchedule)
                self.form.threadInfo.setText("\n".join(lines))
        else:
            self.form.threadInfo.setText("Select the diameter to thread (its cylindrical face) on the Z Range page.")
        self.form.threadWarning.setText(getattr(obj, "SizeWarning", ""))
        self.form.threadWarning.setVisible(bool(getattr(obj, "SizeWarning", "")))

    def registerSignalHandlers(self, obj):
        # Passes and First pass depth are alternatives (a first pass and the
        # degression decide the number of passes): ticking one unticks the other
        set_passes, set_first = self.form.setPasses, self.form.setFirstPassDepth
        set_passes.toggled.connect(lambda on: on and set_first.setChecked(False))
        set_first.toggled.connect(lambda on: on and set_passes.setChecked(False))
        for box, _, widget in SWITCHES:
            getattr(self.form, box).toggled.connect(getattr(self.form, widget).setEnabled)

    def getSignalsForUpdate(self, obj):
        signals = [self.form.useG76.stateChanged, self.form.degression.valueChanged]
        signals += [getattr(self.form, box).stateChanged for box, _, _ in SWITCHES]
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
