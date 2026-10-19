# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
"Install Turning Tools" command: copies the addon's turning tool assets into
the user's CAM asset store.

The CAM tool library only reads its own stores (the user's CamAssets
directory and FreeCAD's built-in assets), not files inside an addon, and the
addon metadata has no content type for tool assets. So, like other addons
that add tools to the user's library, this runs only when the user asks for
it. It adds:

    Assets/Shape/isoshape.fcstd   ISO turning insert shape
    Assets/Shape/isoshape.svg     its icon
    Assets/Bit/CCMT060204R.fctb   example turning insert

No tool library is written; add the bit to a library of your choice.
Assets that already exist in the store are left alone, so user edits are
never overwritten. To pick up a changed asset from the addon, delete the
installed copy and run the command again.
"""

import pathlib

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

ASSET_DIR = pathlib.Path(__file__).resolve().parent.parent / "Assets"

# (asset type, file relative to ASSET_DIR, asset id)
ASSETS = [
    ("toolbitshape", "Shape/isoshape.fcstd", "isoshape"),
    ("toolbitshapesvg", "Shape/isoshape.svg", "isoshape.svg"),
    ("toolbit", "Bit/CCMT060204R.fctb", "CCMT060204R"),
]


def translate(context, text):
    return QtCore.QCoreApplication.translate(context, text)


def install_assets():
    """
    Add any of the addon's assets that are missing from the local CAM store.
    Returns three lists of relative paths: installed, already present, failed.
    """
    from Path.Tool.assets import AssetUri
    from Path.Tool.camassets import cam_assets

    installed, present, failed = [], [], []
    for asset_type, rel_path, asset_id in ASSETS:
        path = ASSET_DIR / rel_path
        try:
            uri = AssetUri.build(asset_type=asset_type, asset_id=asset_id)
            if cam_assets.exists(uri, store="local"):
                present.append(rel_path)
                continue
            cam_assets.add_file(asset_type, path, store="local", asset_id=asset_id)
            installed.append(rel_path)
            FreeCAD.Console.PrintMessage(
                "TurningAddon: installed {} into the CAM asset store\n".format(rel_path))
        except Exception as e:
            failed.append(rel_path)
            FreeCAD.Console.PrintError(
                "TurningAddon: could not install {}: {}\n".format(rel_path, e))
    return installed, present, failed


class CommandTurnInstallTools:
    """Install the addon's turning tool shape and example bit."""

    def GetResources(self):
        return {
            "Pixmap": "CAM-TurnInstallTools",
            "MenuText": QtCore.QT_TRANSLATE_NOOP("CAM_TurnInstallTools", "Install Turning Tools"),
            "ToolTip": QtCore.QT_TRANSLATE_NOOP(
                "CAM_TurnInstallTools",
                "Add the turning insert shape and an example turning tool bit to your CAM tool assets",
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        installed, present, failed = install_assets()
        lines = []
        if installed:
            lines.append(translate("CAM_TurnInstallTools", "Installed:") + "\n  " + "\n  ".join(installed))
        if present:
            lines.append(translate("CAM_TurnInstallTools", "Already present (not changed):") + "\n  " + "\n  ".join(present))
        if failed:
            lines.append(translate("CAM_TurnInstallTools", "Failed (see Report view):") + "\n  " + "\n  ".join(failed))
        lines.append(translate(
            "CAM_TurnInstallTools",
            "Add the example bit to a tool library, or create your own bits from the "
            "ISO Turning Insert shape. Reopen the tool library to see the changes."))
        QtGui.QMessageBox.information(
            FreeCADGui.getMainWindow(),
            translate("CAM_TurnInstallTools", "Install Turning Tools"),
            "\n\n".join(lines))


if FreeCAD.GuiUp:
    FreeCADGui.addCommand("CAM_TurnInstallTools", CommandTurnInstallTools())
