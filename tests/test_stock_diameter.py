# SPDX-License-Identifier: LGPL-2.1-or-later
"""Max Diameter from the stock's exact bounding box, as TurnSpindleAxis places parts."""

import types

import FreeCAD
from PathTurnScripts import PathTurnBase, TurnSpindleAxis

MESH = FreeCAD.BoundBox(-10.004, -10.004, 0, 10.004, 10.004, 50)     # display mesh: a few microns over
EXACT = FreeCAD.BoundBox(-10.0, -10.0, 0, 10.0, 10.0, 50)


class Shape:
    BoundBox = MESH

    def optimalBoundingBox(self, use_triangulation=True, use_tolerance=False):
        assert (use_triangulation, use_tolerance) == (False, False)
        return EXACT


class OldShape:
    BoundBox = MESH


def test_exact_bound_box_and_its_fallback():
    assert TurnSpindleAxis.exact_bound_box(Shape()) is EXACT
    assert TurnSpindleAxis.exact_bound_box(OldShape()) is MESH
    assert TurnSpindleAxis.exact_centre(Shape()) == (0.0, 0.0)


def test_stock_diameter_is_exact(monkeypatch):
    job = types.SimpleNamespace(Stock=types.SimpleNamespace(Shape=Shape()))
    monkeypatch.setattr(PathTurnBase.PathUtils, "findParentJob", lambda obj: job)
    assert PathTurnBase.ObjectOp.stock_diameter(object()) == 20.0
    job.Stock.Shape = OldShape()
    assert abs(PathTurnBase.ObjectOp.stock_diameter(object()) - 20.008) < 1e-9


def test_stock_diameter_without_a_job(monkeypatch):
    monkeypatch.setattr(PathTurnBase.PathUtils, "findParentJob", lambda obj: None)
    assert PathTurnBase.ObjectOp.stock_diameter(object()) is None
