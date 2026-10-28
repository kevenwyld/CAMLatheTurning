# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Install Turning Tools: copies the addon's tool shapes and example bits (ASSETS) into the
user's local CAM asset store, which is the only place the tool library reads."""

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
    ("toolbitshape", "Shape/grooving.fcstd", "grooving"),
    ("toolbitshapesvg", "Shape/grooving.svg", "grooving.svg"),
    ("toolbitshape", "Shape/fullradius.fcstd", "fullradius"),
    ("toolbitshapesvg", "Shape/fullradius.svg", "fullradius.svg"),
    ("toolbitshape", "Shape/threading.fcstd", "threading"),
    ("toolbitshapesvg", "Shape/threading.svg", "threading.svg"),
    ("toolbit", "Bit/Threading_60_partial.fctb", "Threading_60_partial"),
    ("toolbit", "Bit/Groove_4mm_full_radius.fctb", "Groove_4mm_full_radius"),
    ("toolbit", "Bit/GrooveTurn_4mm_lollipop.fctb", "GrooveTurn_4mm_lollipop"),
    ("toolbit", "Bit/BoringBar_10mm_CCMT06.fctb", "BoringBar_10mm_CCMT06"),
    ("toolbit", "Bit/ZTFD0303.fctb", "ZTFD0303"),
]


def translate(context, text):
    return QtCore.QCoreApplication.translate(context, text)


# The shapes and their drawings belong to the addon and are kept up to date;
# tool bits are the user's and are never overwritten.
ADDON_OWNED = ("toolbitshape", "toolbitshapesvg")


def refresh_installed_shapes():
    """Replace installed shapes and drawings that differ from the addon's (run as the CAM
    workbench loads); adds nothing and leaves tool bits alone. Returns the paths updated."""
    from Path.Tool.assets import AssetUri
    from Path.Tool.camassets import cam_assets

    updated = []
    for asset_type, rel_path, asset_id in ASSETS:
        if asset_type not in ADDON_OWNED:
            continue
        path = ASSET_DIR / rel_path
        try:
            uri = AssetUri.build(asset_type=asset_type, asset_id=asset_id)
            if cam_assets.exists(uri, store="local") and cam_assets.get_raw(uri, store="local") != path.read_bytes():
                cam_assets.delete(uri, store="local")
                cam_assets.add_file(asset_type, path, store="local", asset_id=asset_id)
                updated.append(rel_path)
        except Exception as e:
            FreeCAD.Console.PrintLog("TurningAddon: could not refresh {}: {}\n".format(rel_path, e))
    if updated:
        FreeCAD.Console.PrintMessage("TurningAddon: brought {} up to date in the CAM asset store\n".format(
            ", ".join(updated)))
    return updated


def install_assets():
    """Add the addon's assets to the local CAM store: missing ones added, differing shapes
    replaced, existing bits left alone. Returns (installed, updated, present, failed) paths."""
    from Path.Tool.assets import AssetUri
    from Path.Tool.camassets import cam_assets

    installed, updated, present, failed = [], [], [], []
    for asset_type, rel_path, asset_id in ASSETS:
        path = ASSET_DIR / rel_path
        try:
            uri = AssetUri.build(asset_type=asset_type, asset_id=asset_id)
            if cam_assets.exists(uri, store="local"):
                if asset_type in ADDON_OWNED and cam_assets.get_raw(uri, store="local") != path.read_bytes():
                    cam_assets.delete(uri, store="local")
                    cam_assets.add_file(asset_type, path, store="local", asset_id=asset_id)
                    updated.append(rel_path)
                    FreeCAD.Console.PrintMessage(
                        "TurningAddon: updated {} in the CAM asset store\n".format(rel_path))
                else:
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
    return installed, updated, present, failed


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
        installed, updated, present, failed = install_assets()
        lines = []
        if installed:
            lines.append(translate("CAM_TurnInstallTools", "Installed:") + "\n  " + "\n  ".join(installed))
        if updated:
            lines.append(translate("CAM_TurnInstallTools", "Updated to the addon's version:") + "\n  " + "\n  ".join(updated))
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
