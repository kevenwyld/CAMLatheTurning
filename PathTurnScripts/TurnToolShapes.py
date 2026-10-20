# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Registers an ISO turning-insert toolbit shape with the CAM tool library.

Adapted from FreeCAD PR #22335 (dubstar-04 / knipknap). CAM discovers shape and
toolbit classes through __subclasses__(), so importing this module is enough to
register them. The class name must match the Body label in isoshape.fcstd
("Isoshape"), because that's how CAM resolves a shape file to its class.
"""

import FreeCAD
import Path
from typing import Mapping, Optional, Tuple

from Path.Tool.shape.models.base import ToolBitShape
from Path.Tool.toolbit.models.base import ToolBit


class ToolBitShapeIso(ToolBitShape):
    name = "Isoshape"
    aliases = ("isoshape", "iso")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return {
            # CAM's operation base class requires a non-zero Diameter on every
            # tool (Op/Base.py setDefaultValues and execute). Turning ops don't
            # use it; set it to 2 x TipRadius.
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Nominal diameter (2 x tip radius)"),
                "App::PropertyLength",
            ),
            "EdgeLength": (
                FreeCAD.Qt.translate("ToolBitShape", "Cutting edge length"),
                "App::PropertyLength",
            ),
            "Rotation": (
                FreeCAD.Qt.translate("ToolBitShape", "Rotation angle"),
                "App::PropertyAngle",
            ),
            "TipAngle": (
                FreeCAD.Qt.translate("ToolBitShape", "Tip angle"),
                "App::PropertyAngle",
            ),
            "TipRadius": (
                FreeCAD.Qt.translate("ToolBitShape", "Tip radius"),
                "App::PropertyLength",
            ),
        }

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "ISO Turning Insert")


class ToolBitIso(ToolBit):
    SHAPE_CLASS = ToolBitShapeIso

    def __init__(
        self, shape: ToolBitShapeIso, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        Path.Log.track(f"ToolBitIso __init__ shape={shape} id={id}")
        super().__init__(shape, id=id, attrs=attrs)

    @property
    def summary(self) -> str:
        edge = self.get_property_str("EdgeLength", "?")
        tip = self.get_property_str("TipAngle", "?")
        radius = self.get_property_str("TipRadius", "?")
        return FreeCAD.Qt.translate("CAM", f"ISO insert {tip} tip, {edge} edge, R{radius}")


class ToolBitShapeGroove(ToolBitShape):
    """
    Grooving / parting insert: a blade of width Width whose cutting edge is a
    flat bottom with CornerRadius at each end (half the width is a full
    radius insert), with straight flanks. The shape file draws it from its
    reference point at the origin: X at the edge's point closest to the axis,
    Z at the chuck-side flank, the blade extending toward +X and +Z.
    """
    name = "Grooving"
    aliases = ("grooving", "parting")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return {
            "Width": (
                FreeCAD.Qt.translate("ToolBitShape", "Cutting width (S)"),
                "App::PropertyLength",
            ),
            "CornerRadius": (
                FreeCAD.Qt.translate("ToolBitShape", "Corner radius (R); half the width is a full radius"),
                "App::PropertyLength",
            ),
            "CuttingDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Deepest plunge below the surface (La max)"),
                "App::PropertyLength",
            ),
            "TurningDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Largest depth of cut when turning sideways (T)"),
                "App::PropertyLength",
            ),
            # CAM's operation base class requires a non-zero Tool.Diameter
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM; set it to the width"),
                "App::PropertyLength",
            ),
        }

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "Grooving")


class ToolBitGroove(ToolBit):
    SHAPE_CLASS = ToolBitShapeGroove

    def __init__(
        self, shape: ToolBitShapeGroove, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        super().__init__(shape, id=id, attrs=attrs)

    @property
    def summary(self) -> str:
        width = self.get_property_str("Width", "?")
        radius = self.get_property_str("CornerRadius", "?")
        return FreeCAD.Qt.translate("CAM", f"Grooving insert {width} wide, R{radius}")
