# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Rebuild turning tools' 3D models in place from the addon's current shapes.

A tool bit keeps the body it was built with; a newer shape (a holder, an
insert's position) reaches only tools made after it. Rebuilding loads the
tool's shape again from the addon, gives it the tool's own parameter values,
adds any parameters the newer shape has (at their defaults) and rebuilds the
body. The tool controllers and operations keep using the same tool.
"""

import os

import FreeCAD

translate = FreeCAD.Qt.translate

ADDON_SHAPES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Assets", "Shape")


def is_turning_tool(tool):
    from PathTurnScripts.TurnFeedsSpeeds import is_turning_tool as turning
    return turning(tool)


def current_shape(tool):
    """The tool's shape loaded from the addon's own file (what CAM's store is
    refreshed from), else from CAM's store."""
    import pathlib
    from Path.Tool.shape.models.base import ToolBitShape
    path = os.path.join(ADDON_SHAPES, "{}.fcstd".format(tool.ShapeID))
    if os.path.exists(path):
        return ToolBitShape.from_file(pathlib.Path(path))
    return ToolBitShape.resolve_asset(tool.ShapeID)


def rebuild_tool(tool):
    """Rebuild one tool bit's model from its current shape, keeping its values."""
    proxy = tool.Proxy
    shape = current_shape(tool)
    for name in shape.schema():
        if name in tool.PropertiesList:
            shape.set_parameter(name, tool.getPropertyByName(name))
    proxy._tool_bit_shape = shape
    proxy._update_tool_properties()
    proxy._update_visual_representation()


def tools_in(objects):
    """The turning tool bits named by a selection: tool bits themselves, a tool
    controller's tool, or every tool controller's tool in a Job."""
    tools = []

    def add(tool):
        if tool is not None and tool not in tools and hasattr(tool, "ShapeID") and is_turning_tool(tool):
            tools.append(tool)

    for obj in objects:
        if hasattr(obj, "Operations") and hasattr(obj, "Tools"):
            for tc in getattr(obj.Tools, "Group", []) or []:
                add(getattr(tc, "Tool", None))
        elif hasattr(obj, "Tool") and hasattr(obj, "SpindleSpeed"):
            add(obj.Tool)
        else:
            add(obj)
    return tools


def rebuild(tools):
    """Rebuild each tool; returns (rebuilt labels, [(label, error)])."""
    done, failed = [], []
    for tool in tools:
        try:
            rebuild_tool(tool)
            done.append(tool.Label)
        except Exception as e:
            failed.append((tool.Label, str(e)))
    return done, failed


class CommandTurnRebuildTools:
    """Rebuild the selected turning tools' models (a Job's, or the document's)."""

    def GetResources(self):
        from PySide import QtCore
        return {
            "MenuText": QtCore.QT_TRANSLATE_NOOP("CAM_TurnRebuildTools", "Rebuild Turning Tool Models"),
            "ToolTip": QtCore.QT_TRANSLATE_NOOP(
                "CAM_TurnRebuildTools",
                "Rebuild the 3D models of turning tools from the addon's current shapes, keeping their values: "
                "the selected tool controllers or tools, every tool of a selected Job, or with nothing selected "
                "every turning tool in the document"),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        import FreeCADGui
        from PySide import QtGui
        doc = FreeCAD.ActiveDocument
        title = translate("CAM_TurnRebuildTools", "Rebuild Turning Tool Models")
        selection = FreeCADGui.Selection.getSelection()
        tools = tools_in(selection if selection else doc.Objects)
        if not tools:
            QtGui.QMessageBox.information(FreeCADGui.getMainWindow(), title, translate(
                "CAM_TurnRebuildTools", "No turning tools in the selection or the document"))
            return
        doc.openTransaction(title)
        try:
            done, failed = rebuild(tools)
        finally:
            doc.commitTransaction()
        doc.recompute()
        lines = []
        if done:
            lines.append(translate("CAM_TurnRebuildTools", "Rebuilt:") + "\n  " + "\n  ".join(done))
        if failed:
            lines.append(translate("CAM_TurnRebuildTools", "Not rebuilt:") + "\n  " +
                         "\n  ".join("{}: {}".format(label, error) for label, error in failed))
        QtGui.QMessageBox.information(FreeCADGui.getMainWindow(), title, "\n\n".join(lines))


if FreeCAD.GuiUp:
    import FreeCADGui
    FreeCADGui.addCommand("CAM_TurnRebuildTools", CommandTurnRebuildTools())
