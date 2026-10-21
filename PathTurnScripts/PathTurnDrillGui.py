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

    def _spinboxes(self, obj):
        if getattr(self, "_boxes", None) is None:
            self._boxes = [PathGuiUtil.QuantitySpinBox(self.form.peckDepth, obj, "PeckDepth"),
                           PathGuiUtil.QuantitySpinBox(self.form.retractHeight, obj, "RetractHeight")]
        return self._boxes

    def getFields(self, obj):
        if self.form.cycle.currentText() and obj.Cycle != self.form.cycle.currentText():
            obj.Cycle = self.form.cycle.currentText()
        for box in self._spinboxes(obj):
            box.updateProperty()
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

    def updateData(self, obj, prop):
        if prop in ("DrillReport", "Cycle") and hasattr(self, "form"):
            self.show_report(obj)
            self.show_fields(obj)

    def registerSignalHandlers(self, obj):
        self.form.cycle.currentIndexChanged.connect(lambda _: self.show_fields(obj))

    def getSignalsForUpdate(self, obj):
        return [self.form.cycle.currentIndexChanged, self.form.peckDepth.editingFinished,
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
