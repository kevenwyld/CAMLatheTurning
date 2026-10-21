# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI for the Turn Drill operation."""
import FreeCAD
import FreeCADGui
import Path.Base.Gui.Util as PathGuiUtil
import Path.Op.Gui.Base as PathOpGui
import PathTurnScripts.PathTurnAddonHelpers as PathTurnHelpers
import PathTurnScripts.PathTurnBaseGui as PathTurnBaseGui
import PathTurnScripts.PathTurnDrill as PathTurnDrill

from PySide import QtCore


class TaskPanelOpPage(PathTurnBaseGui.TaskPanelTurnBase):
    '''Page controller for the Turn Drill operation: its own form.'''

    def getForm(self):
        return FreeCADGui.PySideUic.loadUi(PathTurnHelpers.getResourcePath("PageOpTurnDrillEdit.ui"))

    # a checkbox that sets a value by hand: (checkbox, switch, property, field)
    SWITCHES = (("setHoleStart", "SetHoleStart", "HoleStart", "holeStart"),
                ("setHoleDepth", "SetHoleDepth", "HoleDepth", "holeDepth"))

    def _spinboxes(self, obj):
        if getattr(self, "_boxes", None) is None:
            self._boxes = [PathGuiUtil.QuantitySpinBox(self.form.peckDepth, obj, "PeckDepth"),
                           PathGuiUtil.QuantitySpinBox(self.form.retractHeight, obj, "RetractHeight")]
            self._switched = {prop: PathGuiUtil.QuantitySpinBox(getattr(self.form, field), obj, prop)
                              for _, _, prop, field in self.SWITCHES}
        return self._boxes

    def refresh_switched(self, obj):
        '''The worked-out (greyed) values follow the op; values set by hand are left alone.'''
        self._spinboxes(obj)
        for box, switch, prop, field in self.SWITCHES:
            check = getattr(self.form, box)
            check.blockSignals(True)
            check.setChecked(bool(getattr(obj, switch)))
            check.blockSignals(False)
            getattr(self.form, field).setEnabled(bool(getattr(obj, switch)))
            if not getattr(obj, switch):
                self._switched[prop].updateWidget()

    def getFields(self, obj):
        if self.form.cycle.currentText() and obj.Cycle != self.form.cycle.currentText():
            obj.Cycle = self.form.cycle.currentText()
        for box in self._spinboxes(obj):
            box.updateProperty()
        for box, switch, prop, _ in self.SWITCHES:
            if getattr(obj, switch) != getattr(self.form, box).isChecked():
                setattr(obj, switch, getattr(self.form, box).isChecked())
            if getattr(obj, switch):
                self._switched[prop].updateProperty()
        if abs(obj.DwellTime - self.form.dwellTime.value()) > 1e-9:
            obj.DwellTime = self.form.dwellTime.value()
        for widget, prop in ((self.form.depthToTip, "DepthToTip"), (self.form.useCannedCycle, "UseCannedCycle")):
            if getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())

    def setFields(self, obj):
        self.form.cycle.blockSignals(True)
        self.form.cycle.clear()
        self.form.cycle.addItems(obj.getEnumerationsOfProperty("Cycle"))
        self.form.cycle.setCurrentText(obj.Cycle)
        self.form.cycle.blockSignals(False)
        for box in self._spinboxes(obj):
            box.updateWidget()
        self.form.dwellTime.setValue(obj.DwellTime)
        self.form.depthToTip.setChecked(obj.DepthToTip)
        self.form.useCannedCycle.setChecked(obj.UseCannedCycle)
        for box in self._switched.values():
            box.updateWidget()
        self.refresh_switched(obj)
        self.show_fields(obj)
        self.show_report(obj)

    def show_fields(self, obj):
        code = PathTurnDrill.CODE.get(obj.Cycle, "G83")
        for widget in (self.form.peckDepth, self.form.label_peck):
            widget.setEnabled(code in ("G83", "G73"))
        for widget in (self.form.dwellTime, self.form.label_dwell):
            widget.setEnabled(code == "G82")

    def show_report(self, obj):
        if getattr(obj, "DrillReport", ""):
            self.form.drillReport.setText(obj.DrillReport)
        elif not self.form.setHoleDepth.isChecked():
            self.form.drillReport.setText("Select the hole to drill (its cylindrical face) on the Z Range page, or "
                                          "tick Hole depth and set it.")

    def updateData(self, obj, prop):
        if prop in ("DrillReport", "Cycle") and hasattr(self, "form"):
            self.show_report(obj)
            self.show_fields(obj)
        if prop in ("HoleStart", "HoleDepth", "SetHoleStart", "SetHoleDepth") and hasattr(self, "form"):
            self.refresh_switched(obj)

    def registerSignalHandlers(self, obj):
        self.form.cycle.currentIndexChanged.connect(lambda _: self.show_fields(obj))
        for box, _, _, field in self.SWITCHES:
            getattr(self.form, box).toggled.connect(getattr(self.form, field).setEnabled)

    def getSignalsForUpdate(self, obj):
        return [self.form.setHoleStart.stateChanged, self.form.setHoleDepth.stateChanged,
                self.form.holeStart.editingFinished, self.form.holeDepth.editingFinished,
                self.form.cycle.currentIndexChanged, self.form.peckDepth.editingFinished,
                self.form.dwellTime.valueChanged, self.form.retractHeight.editingFinished,
                self.form.depthToTip.stateChanged, self.form.useCannedCycle.stateChanged]


Command = PathOpGui.SetupOperation('TurnDrill',
                                   PathTurnDrill.Create,
                                   TaskPanelOpPage,
                                   'CAM-TurnDrill',
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnDrill", "Turn Drill"),
                                   QtCore.QT_TRANSLATE_NOOP("PathTurnDrill",
                                                            "Drills the selected hole on the spindle axis (peck, chip break, drill or dwell cycle)"),
                                   PathTurnDrill.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathTurnDrillGui... done\n")
