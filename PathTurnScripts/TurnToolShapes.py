# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""The turning tool shapes (ISO insert, grooving, full radius, threading) for CAM's tool
library; importing registers them (CAM finds subclasses). Class names match the shape files'
Body labels. Adapted from FreeCAD PR #22335."""

import FreeCAD
import Path
from typing import Any, Mapping, Optional, Tuple

from Path.Tool.shape.models.base import ToolBitShape
from Path.Tool.toolbit.models.base import ToolBit
from Path.Tool.toolbit.mixins import CuttingToolMixin


def init_turning_toolbit(toolbit, cutting=True):
    '''Cutting properties for an insert: Chipload (one edge: the feed per revolution) and
    Carbide by default; a threading insert gets no Chipload.'''
    if cutting:
        toolbit._init_cutting_properties(toolbit.obj)
    if getattr(toolbit.obj, "Material", None) == "HSS":
        toolbit.obj.Material = "Carbide"


def _mm(value) -> float:
    """A parameter's magnitude, whether it arrives as a Quantity or a number."""
    return float(value.Value if hasattr(value, "Value") else value)


def holder_schema():
    """The holder drawn with an insert (visual only: the simulation shows it;
    paths and collision checks use the insert): ISO 13399's names."""
    tr = FreeCAD.Qt.translate
    return {
        "Shank": (tr("ToolBitShape", "Draw a turning shank with the insert (visual only)"), "App::PropertyBool"),
        "BoringBar": (tr("ToolBitShape", "Draw a boring bar with the insert (visual only)"), "App::PropertyBool"),
        "ShankWidth": (tr("ToolBitShape", "Shank width (ISO B)"), "App::PropertyLength"),
        "ShankHeight": (tr("ToolBitShape", "Shank height (ISO H)"), "App::PropertyLength"),
        "BarDiameter": (tr("ToolBitShape", "Boring bar diameter (ISO DCON)"), "App::PropertyLength"),
        "HolderLength": (tr("ToolBitShape", "Holder length behind the cutting point (ISO LF)"), "App::PropertyLength"),
        "TipOffset": (tr("ToolBitShape",
                         "Tip offset (ISO WF): the cutting point to the shank's back side, or to the bar's centre line"),
                      "App::PropertyLength"),
    }


class ToolBitShapeIso(ToolBitShape):
    name = "Isoshape"
    aliases = ("isoshape", "iso")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return dict({
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
        }, **holder_schema())

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


class ToolBitIso(ToolBit, CuttingToolMixin):
    SHAPE_CLASS = ToolBitShapeIso

    def __init__(
        self, shape: ToolBitShapeIso, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        Path.Log.track(f"ToolBitIso __init__ shape={shape} id={id}")
        super().__init__(shape, id=id, attrs=attrs)
        init_turning_toolbit(self, cutting=True)

    @property
    def summary(self) -> str:
        edge = self.get_property_str("EdgeLength", "?")
        tip = self.get_property_str("TipAngle", "?")
        radius = self.get_property_str("TipRadius", "?")
        return FreeCAD.Qt.translate("CAM", f"ISO insert {tip} tip, {edge} edge, R{radius}")


class ToolBitShapeGroove(ToolBitShape):
    """Grooving / parting insert: a blade of Width with CornerRadius at each end, drawn
    from its reference point (X the edge's point nearest the axis, Z the chuck-side flank)."""
    name = "Grooving"
    aliases = ("grooving", "parting")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return dict({
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
        }, **holder_schema())

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """CAM needs a tool Diameter; derive it from the width (kept out of the editor)."""
        return {"Diameter": lambda p: _mm(p["Width"])}

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "Grooving")


class ToolBitGroove(ToolBit, CuttingToolMixin):
    SHAPE_CLASS = ToolBitShapeGroove

    def __init__(
        self, shape: ToolBitShapeGroove, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        super().__init__(shape, id=id, attrs=attrs)
        init_turning_toolbit(self, cutting=True)

    @property
    def summary(self) -> str:
        width = self.get_property_str("Width", "?")
        radius = self.get_property_str("CornerRadius", "?")
        return FreeCAD.Qt.translate("CAM", f"Grooving insert {width} wide, R{radius}")


class ToolBitShapeFullRadius(ToolBitShape):
    """Full radius insert: a blade of Width ending in a radius of half the width, on a neck
    of NeckWidth (less than Width: a lollipop) with SideRelief on tangent flanks. Same reference
    point as the grooving insert; GroovingDepth is ISO CDX, TurningDepth APMX."""
    name = "FullRadius"
    aliases = ("fullradius", "full_radius")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return dict({
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
            "NeckWidth": (
                FreeCAD.Qt.translate("ToolBitShape",
                                     "Width of the body behind the head (ISO BW): the width itself for tangent "
                                     "flanks, less for a lollipop groove-turn insert"),
                "App::PropertyLength",
            ),
            "SideRelief": (
                FreeCAD.Qt.translate("ToolBitShape",
                                     "Flank relief (α) for tangent flanks (Neck width = Width): they lean inward by "
                                     "this angle from the head. A lollipop's neck is straight: it does not cut"),
                "App::PropertyAngle",
            ),
            "Diameter": (
                FreeCAD.Qt.translate("ToolBitShape", "Required by CAM, not used for turning; follows the width"),
                "App::PropertyLength",
            ),
        }, **holder_schema())

    @classmethod
    def derived_parameters(cls) -> Mapping[str, Any]:
        """CAM needs a tool Diameter; derive it from the width (kept out of the editor)."""
        return {"Diameter": lambda p: _mm(p["Width"])}

    @property
    def label(self) -> str:
        return FreeCAD.Qt.translate("ToolBitShape", "Full Radius")


class ToolBitFullRadius(ToolBit, CuttingToolMixin):
    SHAPE_CLASS = ToolBitShapeFullRadius

    def __init__(
        self, shape: ToolBitShapeFullRadius, id: Optional[str] = None, attrs: Optional[Mapping] = None
    ):
        super().__init__(shape, id=id, attrs=attrs)
        init_turning_toolbit(self, cutting=True)

    @property
    def summary(self) -> str:
        width = self.get_property_str("Width", "?")
        return FreeCAD.Qt.translate("CAM", f"Full radius insert {width} wide")


class ToolBitShapeThreading(ToolBitShape):
    """Threading insert: a profile of ProfileAngle with TipRadius, drawn from its reference
    point, the profile's theoretical sharp point (which Turn Thread programs)."""
    name = "Threading"
    aliases = ("threading", "thread")

    @classmethod
    def schema(cls) -> Mapping[str, Tuple[str, str]]:
        return dict({
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
        }, **holder_schema())

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
        init_turning_toolbit(self, cutting=False)

    @property
    def summary(self) -> str:
        angle = self.get_property_str("ProfileAngle", "?")
        return FreeCAD.Qt.translate("CAM", f"Threading insert {angle}")
