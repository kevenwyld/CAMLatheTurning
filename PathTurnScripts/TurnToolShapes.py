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
from typing import Any, Mapping, Optional, Tuple

from Path.Tool.shape.models.base import ToolBitShape
from Path.Tool.toolbit.models.base import ToolBit


def _mm(value) -> float:
    """A parameter's magnitude, whether it arrives as a Quantity or a number."""
    return float(value.Value if hasattr(value, "Value") else value)


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
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM, not used for turning; twice the tip radius"),
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

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """
        CAM's operations need a tool Diameter; the turning operations do not
        use it. Derive it (the nose diameter) so it is kept out of the editor,
        as CAM does for the chamfer mill's diameter.
        """
        return {"Diameter": lambda p: 2 * _mm(p["TipRadius"])}

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
    flat bottom with CornerRadius at each end (at most half the width), with
    straight flanks. The shape file draws it from its reference point at the
    origin: X at the edge's point closest to the axis, Z at the chuck-side
    flank, the blade extending toward +X and +Z.
    """
    name = "Grooving"
    aliases = ("grooving", "parting")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return {
            "Width": (FreeCAD.Qt.translate("ToolBitShape", "Cutting width (S)"), "App::PropertyLength"),
            "CornerRadius": (
                FreeCAD.Qt.translate("ToolBitShape", "Corner radius (R), at most half the width"),
                "App::PropertyLength",
            ),
            "GroovingDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Deepest plunge before the holder would touch (La max)"),
                "App::PropertyLength",
            ),
            "TurningDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Largest depth of cut when turning sideways (T)"),
                "App::PropertyLength",
            ),
            # CAM's operation base class requires a non-zero Tool.Diameter;
            # derived from the width (see derived_parameters), so not edited
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM, not used for turning; follows the width"),
                "App::PropertyLength",
            ),
        }

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """CAM needs a tool Diameter; derive it from the width (kept out of the editor)."""
        return {"Diameter": lambda p: _mm(p["Width"])}

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


class ToolBitShapeFullRadius(ToolBitShape):
    """
    Full radius insert: a blade of width Width ending in a semicircle of
    radius Width / 2, with straight flanks. Drawn from the same reference
    point as the grooving insert (X at the bottom of the radius, Z at the
    chuck-side flank).
    """
    name = "FullRadius"
    aliases = ("fullradius", "full_radius")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return {
            "Width": (
                FreeCAD.Qt.translate("ToolBitShape", "Cutting width (S); the end is a radius of half the width"),
                "App::PropertyLength",
            ),
            "GroovingDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Deepest plunge before the holder would touch (La max)"),
                "App::PropertyLength",
            ),
            "TurningDepth": (
                FreeCAD.Qt.translate("ToolBitShape", "Largest depth of cut when turning sideways (T)"),
                "App::PropertyLength",
            ),
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM, not used for turning; follows the width"),
                "App::PropertyLength",
            ),
        }

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """CAM needs a tool Diameter; derive it from the width (kept out of the editor)."""
        return {"Diameter": lambda p: _mm(p["Width"])}

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "Full Radius")


class ToolBitFullRadius(ToolBit):
    SHAPE_CLASS = ToolBitShapeFullRadius

    def __init__(
        self, shape: ToolBitShapeFullRadius, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        super().__init__(shape, id=id, attrs=attrs)

    @property
    def summary(self) -> str:
        width = self.get_property_str("Width", "?")
        return FreeCAD.Qt.translate("CAM", f"Full radius insert {width} wide")


class ToolBitShapeThreading(ToolBitShape):
    """
    Threading insert: a profile of ProfileAngle with TipRadius at its tip.
    The shape file draws it from its reference point at the origin: the
    theoretical sharp point of the profile, which thread depths are measured
    to and Turn Thread programs. The insert extends toward +X.
    """
    name = "Threading"
    aliases = ("threading", "thread")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return {
            "ProfileAngle": (
                FreeCAD.Qt.translate("ToolBitShape", "Included angle of the thread profile (60 metric and Unified)"),
                "App::PropertyAngle",
            ),
            "TipRadius": (FreeCAD.Qt.translate("ToolBitShape", "Radius at the tip of the profile"), "App::PropertyLength"),
            "Width": (FreeCAD.Qt.translate("ToolBitShape", "Width of the insert (for display)"), "App::PropertyLength"),
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM, not used for turning; follows the width"),
                "App::PropertyLength",
            ),
        }

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """CAM needs a tool Diameter; derive it from the width (kept out of the editor)."""
        return {"Diameter": lambda p: _mm(p["Width"])}

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "Threading")


class ToolBitThreading(ToolBit):
    SHAPE_CLASS = ToolBitShapeThreading

    def __init__(
        self, shape: ToolBitShapeThreading, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        super().__init__(shape, id=id, attrs=attrs)

    @property
    def summary(self) -> str:
        angle = self.get_property_str("ProfileAngle", "?")
        return FreeCAD.Qt.translate("CAM", f"Threading insert {angle}")
