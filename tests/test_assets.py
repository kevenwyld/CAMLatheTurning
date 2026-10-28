# SPDX-License-Identifier: LGPL-2.1-or-later
"""TurnAssets: the addon's shapes are refreshed in CAM's store without losing the user's copy."""

import pathlib
import sys
import types

import FreeCAD
from PathTurnScripts import TurnAssets

STAMP = "20261028-120000"


class Store:
    """CAM's asset manager, local store only: exists, get_raw, add_raw (create or overwrite)."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.deleted = []

    @staticmethod
    def uri(asset_type, asset_id):
        return "{}://{}".format(asset_type, asset_id)

    def exists(self, uri, store):
        return uri in self.files

    def get_raw(self, uri, store):
        return self.files[uri]

    def add_raw(self, asset_type, asset_id, data, store):
        self.files[self.uri(asset_type, asset_id)] = data

    def delete(self, uri, store):
        self.deleted.append(uri)
        del self.files[uri]


def addon_bytes(rel_path):
    return (TurnAssets.ASSET_DIR / rel_path).read_bytes()


def test_refresh_keeps_a_differing_copy_and_replaces_it():
    FreeCAD.Console.messages = []
    store = Store({"toolbitshape://isoshape": b"edited by the user",
                   "toolbitshapesvg://grooving.svg": addon_bytes("Shape/grooving.svg"),
                   "toolbit://CCMT060204R": b"user's bit"})
    updated = TurnAssets.refresh_installed_shapes(store, Store.uri, STAMP)
    assert updated == ["Shape/isoshape.fcstd"]
    assert store.files["toolbitshape://isoshape"] == addon_bytes("Shape/isoshape.fcstd")
    assert store.files["toolbitshape://isoshape.bak." + STAMP] == b"edited by the user"
    assert store.files["toolbit://CCMT060204R"] == b"user's bit"
    assert not store.deleted
    assert len(store.files) == 4          # nothing added that was not installed
    messages = FreeCAD.Console.of("message")
    assert len(messages) == 1 and "isoshape.bak." + STAMP in messages[0]


def test_refresh_of_matching_shapes_changes_nothing():
    files = {"toolbitshape://grooving": addon_bytes("Shape/grooving.fcstd")}
    store = Store(files)
    assert TurnAssets.refresh_installed_shapes(store, Store.uri, STAMP) == []
    assert store.files == files


def test_install_adds_missing_assets_backs_up_shapes_and_leaves_bits():
    FreeCAD.Console.messages = []
    store = Store({"toolbitshape://threading": b"old shape", "toolbit://ZTFD0303": b"user's bit"})
    installed, updated, present, failed, backups = TurnAssets.install_assets(store, Store.uri, STAMP)
    assert updated == ["Shape/threading.fcstd"] and present == ["Bit/ZTFD0303.fctb"] and not failed
    assert len(installed) == len(TurnAssets.ASSETS) - 2
    assert backups == ["toolbitshape://threading.bak." + STAMP]
    assert store.files["toolbitshape://threading.bak." + STAMP] == b"old shape"
    assert store.files["toolbit://ZTFD0303"] == b"user's bit"
    assert not store.deleted


def test_a_store_error_is_reported_not_raised():
    class Broken(Store):
        def get_raw(self, uri, store):
            raise OSError("disk")

    FreeCAD.Console.messages = []
    store = Broken({"toolbitshape://isoshape": b"x"})
    assert TurnAssets.refresh_installed_shapes(store, Store.uri, STAMP) == []
    assert store.files == {"toolbitshape://isoshape": b"x"}
    assert any("disk" in m for m in FreeCAD.Console.of("log"))


def test_store_path_follows_cams_mapping(monkeypatch):
    prefs = types.SimpleNamespace(getAssetPath=lambda: pathlib.Path("/home/u/CAM"))
    camassets = types.SimpleNamespace(asset_mapping={"toolbitshape": "Tools/Shape/{asset_id}.fcstd"})
    monkeypatch.setattr(sys.modules["Path"], "Preferences", prefs, raising=False)
    monkeypatch.setattr(sys.modules["Path.Tool"], "camassets", camassets, raising=False)
    path = TurnAssets.store_path("toolbitshape", "isoshape.bak." + STAMP)
    assert pathlib.Path(path) == pathlib.Path("/home/u/CAM/Tools/Shape/isoshape.bak.%s.fcstd" % STAMP)


def test_backups_go_to_a_folder_the_library_does_not_list(monkeypatch, tmp_path):
    prefs = types.SimpleNamespace(getAssetPath=lambda: tmp_path)
    camassets = types.SimpleNamespace(asset_mapping={"toolbitshape": "Tools/Shape/{asset_id}.fcstd",
                                                     "toolbitshapesvg": "Tools/Shape/{asset_id}"})
    monkeypatch.setattr(sys.modules["Path"], "Preferences", prefs, raising=False)
    monkeypatch.setattr(sys.modules["Path.Tool"], "camassets", camassets, raising=False)
    store = Store({"toolbitshape://isoshape": b"edited by the user",
                   "toolbitshapesvg://isoshape.svg": b"<svg/>"})
    assert TurnAssets.refresh_installed_shapes(store, Store.uri, STAMP) == ["Shape/isoshape.fcstd", "Shape/isoshape.svg"]
    kept = tmp_path / "Backup" / "CAMLatheTurning"
    assert (kept / ("isoshape.fcstd." + STAMP)).read_bytes() == b"edited by the user"
    assert (kept / ("isoshape.svg." + STAMP)).read_bytes() == b"<svg/>"
    assert not [u for u in store.files if ".bak." in u]          # nothing extra in the store
    assert store.files["toolbitshape://isoshape"] == addon_bytes("Shape/isoshape.fcstd")
