# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Install Turning Tools: copies the addon's tool shapes and example bits (ASSETS) into the
user's local CAM asset store, which is the only place the tool library reads."""

import pathlib
import time

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


def replace_installed(assets, uri, asset_type, asset_id, data, stamp):
    """Replace an installed asset that differs from data, first keeping the installed copy as a
    backup. Returns where the copy was kept, or None when it already matched."""
    old = assets.get_raw(uri, store="local")
    if old == data:
        return None
    kept = backup_file(asset_type, asset_id, stamp)
    if kept is not None:
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_bytes(old)
        kept = str(kept)
    else:
        # the store's folder is unknown: keep the copy in the store under another id
        backup_id = "{}.bak.{}".format(asset_id, stamp)
        assets.add_raw(asset_type, backup_id, old, store="local")
        kept = store_path(asset_type, backup_id)
    assets.add_raw(asset_type, asset_id, data, store="local")
    return kept


BACKUP_DIR = "Backup/CAMLatheTurning"     # under the CAM asset folder: no store pattern matches it


def store_file(asset_type, asset_id):
    """The local store's file for an asset (pathlib.Path), or None when that cannot be worked out."""
    try:
        from Path import Preferences
        from Path.Tool import camassets
        return Preferences.getAssetPath() / camassets.asset_mapping[asset_type].format(asset_id=asset_id)
    except Exception:
        return None


def store_path(asset_type, asset_id):
    """Where the local store keeps an asset, for messages (its URI if that cannot be worked out)."""
    path = store_file(asset_type, asset_id)
    return "{}://{}".format(asset_type, asset_id) if path is None else str(path)


def backup_file(asset_type, asset_id, stamp):
    """Where an installed asset's copy is kept: <asset folder>/Backup/CAMLatheTurning/<file>.<stamp>,
    which the tool library does not list. None when the store's folder is unknown."""
    path = store_file(asset_type, asset_id)
    if path is None:
        return None
    from Path import Preferences
    return Preferences.getAssetPath() / BACKUP_DIR / "{}.{}".format(path.name, stamp)


def _report_backup(rel_path, kept):
    FreeCAD.Console.PrintMessage("TurningAddon: {} differed from the addon's; replaced, your copy kept as {}\n".format(
        rel_path, kept))


def refresh_installed_shapes(assets=None, build_uri=None, stamp=None):
    """Bring installed shapes and drawings that differ from the addon's up to date (run as the
    CAM workbench loads), keeping a backup of each; adds nothing. Returns the paths updated."""
    if assets is None:
        from Path.Tool.assets import AssetUri
        from Path.Tool.camassets import cam_assets
        assets, build_uri = cam_assets, AssetUri.build
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    updated = []
    for asset_type, rel_path, asset_id in ASSETS:
        if asset_type not in ADDON_OWNED:
            continue
        try:
            uri = build_uri(asset_type=asset_type, asset_id=asset_id)
            if not assets.exists(uri, store="local"):
                continue
            kept = replace_installed(assets, uri, asset_type, asset_id, (ASSET_DIR / rel_path).read_bytes(), stamp)
            if kept:
                updated.append(rel_path)
                _report_backup(rel_path, kept)
        except Exception as e:
            FreeCAD.Console.PrintLog("TurningAddon: could not refresh {}: {}\n".format(rel_path, e))
    return updated


def install_assets(assets=None, build_uri=None, stamp=None):
    """Add the addon's assets to the local CAM store: missing ones added, differing shapes replaced
    (backed up first), bits left alone. Returns (installed, updated, present, failed, backups) paths."""
    if assets is None:
        from Path.Tool.assets import AssetUri
        from Path.Tool.camassets import cam_assets
        assets, build_uri = cam_assets, AssetUri.build
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    installed, updated, present, failed, backups = [], [], [], [], []
    for asset_type, rel_path, asset_id in ASSETS:
        path = ASSET_DIR / rel_path
        try:
            uri = build_uri(asset_type=asset_type, asset_id=asset_id)
            if assets.exists(uri, store="local"):
                kept = None
                if asset_type in ADDON_OWNED:
                    kept = replace_installed(assets, uri, asset_type, asset_id, path.read_bytes(), stamp)
                if kept:
                    updated.append(rel_path)
                    backups.append(kept)
                    _report_backup(rel_path, kept)
                else:
                    present.append(rel_path)
                continue
            assets.add_raw(asset_type, asset_id, path.read_bytes(), store="local")
            installed.append(rel_path)
            FreeCAD.Console.PrintMessage(
                "TurningAddon: installed {} into the CAM asset store\n".format(rel_path))
        except Exception as e:
            failed.append(rel_path)
            FreeCAD.Console.PrintError(
                "TurningAddon: could not install {}: {}\n".format(rel_path, e))
    return installed, updated, present, failed, backups


class CommandTurnInstallTools:
    """Install the addon's turning tool shape and example bit."""

    def GetResources(self):
        return {
            "Pixmap": "CAM-TurnInstallTools",
            "MenuText": QtCore.QT_TRANSLATE_NOOP("CAM_TurnInstallTools", "Install Turning Tools"),
            "ToolTip": QtCore.QT_TRANSLATE_NOOP(
                "CAM_TurnInstallTools",
                "Add the addon's turning tool shapes and example bits to your CAM tool assets",
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        installed, updated, present, failed, backups = install_assets()
        lines = []
        if installed:
            lines.append(translate("CAM_TurnInstallTools", "Installed:") + "\n  " + "\n  ".join(installed))
        if updated:
            lines.append(translate("CAM_TurnInstallTools", "Updated to the addon's version:") + "\n  " + "\n  ".join(updated))
            lines.append(translate("CAM_TurnInstallTools", "Your copies were kept:") + "\n  " + "\n  ".join(backups))
        if present:
            lines.append(translate("CAM_TurnInstallTools", "Already present (not changed):") + "\n  " + "\n  ".join(present))
        if failed:
            lines.append(translate("CAM_TurnInstallTools", "Failed (see Report view):") + "\n  " + "\n  ".join(failed))
        lines.append(translate(
            "CAM_TurnInstallTools",
            "Add the example bits to a tool library, or make your own from the shapes. "
            "Reopen the tool library to see them.\n\n"
            "The shapes and their drawings are the addon's: when the CAM workbench loads, or here, a copy in "
            "your store that differs is replaced, and yours is kept in Backup/CAMLatheTurning in your CAM asset folder. "
            "Tool bits are never changed."))
        QtGui.QMessageBox.information(
            FreeCADGui.getMainWindow(),
            translate("CAM_TurnInstallTools", "Install Turning Tools"),
            "\n\n".join(lines))


if FreeCAD.GuiUp:
    FreeCADGui.addCommand("CAM_TurnInstallTools", CommandTurnInstallTools())
