# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stand-ins for the FreeCAD, CAM, PySide and liblathe modules the addon imports, so its
pure logic can be tested headless. They implement only what the tests reach."""

import sys
import types


class Console:
    messages = []

    @classmethod
    def _add(cls, kind, text):
        cls.messages.append((kind, text))

    @classmethod
    def PrintError(cls, text):
        cls._add("error", text)

    @classmethod
    def PrintWarning(cls, text):
        cls._add("warning", text)

    @classmethod
    def PrintMessage(cls, text):
        cls._add("message", text)

    @classmethod
    def PrintLog(cls, text):
        cls._add("log", text)

    @classmethod
    def of(cls, kind):
        return [text for k, text in cls.messages if k == kind]


class Quantity:
    def __init__(self, value=0.0, unit=None):
        self.Value = float(value)
        self.Unit = unit

    @property
    def UserString(self):
        return "%g mm" % self.Value

    def __float__(self):
        return self.Value


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class BoundBox:
    def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
        self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = xmin, ymin, zmin, xmax, ymax, zmax

    XLength = property(lambda self: self.XMax - self.XMin)
    YLength = property(lambda self: self.YMax - self.YMin)
    ZLength = property(lambda self: self.ZMax - self.ZMin)
    Center = property(lambda self: Vector((self.XMin + self.XMax) / 2, (self.YMin + self.YMax) / 2,
                                          (self.ZMin + self.ZMax) / 2))


class Command:
    def __init__(self, name, parameters=None, annotations=None):
        self.Name = name
        self.Parameters = dict(parameters or {})
        self.Annotations = dict(annotations or {})


class ObjectOp:
    """Path.Op.Base.ObjectOp: the turning ops' base class."""

    def onChanged(self, obj, prop):
        pass

    def onDocumentRestored(self, obj):
        pass

    def opOnDocumentRestored(self, obj):
        pass


def module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    parent, _, child = name.rpartition(".")
    if parent in sys.modules:
        setattr(sys.modules[parent], child, mod)
    return mod


def _noop(*args, **kwargs):
    return None


def install():
    """Put the stand-ins into sys.modules (before importing any addon module)."""
    Console.messages = []
    units = types.SimpleNamespace(Quantity=Quantity, Length="Length")
    module("FreeCAD", Console=Console, Units=units, Vector=Vector, BoundBox=BoundBox, GuiUp=False,
           ActiveDocument=None, Qt=types.SimpleNamespace(translate=lambda context, text, *a: text))
    module("FreeCADGui", addCommand=_noop, addIconPath=_noop, addWorkbenchManipulator=_noop,
           getMainWindow=_noop)
    module("Part", Circle=type("Circle", (), {}), Cylinder=type("Cylinder", (), {}))

    module("Path", Command=Command)
    module("Path.Log", setLevel=_noop, trackModule=_noop, track=_noop, debug=_noop, thisModule=lambda: "",
           Level=types.SimpleNamespace(DEBUG=0, INFO=1, NOTICE=2))
    module("Path.Op")
    features = {name: 1 << i for i, name in enumerate(
        ("FeatureTool", "FeatureDepths", "FeatureHeights", "FeatureStartPoint", "FeatureFinishDepth",
         "FeatureStepDown", "FeatureNoFinalDepth", "FeatureBaseVertexes", "FeatureBaseEdges",
         "FeatureBaseFaces", "FeatureBasePanels", "FeatureLocations", "FeatureCoolant", "FeatureDiameters",
         "FeatureBaseModels"))}
    features["FeatureBaseGeometry"] = (features["FeatureBaseVertexes"] | features["FeatureBaseEdges"]
                                       | features["FeatureBaseFaces"] | features["FeatureBasePanels"])
    module("Path.Op.Base", ObjectOp=ObjectOp, **features)
    module("Path.Tool")
    module("Path.Tool.FeedsSpeeds", MaterialContext=object, OpContext=object, ToolContext=object,
           derive_preset_label=_noop, get_presets=lambda tool: [])
    module("Path.Tool.FeedsSpeeds.providers", MachinabilityProvider=object, ToolPresetProvider=object,
           _score_preset=_noop)
    module("PathScripts")
    module("PathScripts.PathUtils", findParentJob=lambda obj: None)

    translate = staticmethod(lambda context, text, disambig=None: text)
    module("PySide")
    module("PySide.QtCore", QCoreApplication=type("QCoreApplication", (), {"translate": translate}),
           QT_TRANSLATE_NOOP=lambda context, text: text)
    module("PySide.QtGui", QMessageBox=types.SimpleNamespace(information=_noop))

    # liblathe: the addon imports these names at module level; the tests do not use them
    module("liblathe")
    module("liblathe.base")
    module("liblathe.base.point", Point=type("Point", (), {"__init__": lambda self, x=0, y=0, z=0: None}))
    module("liblathe.base.segment", Segment=type("Segment", (), {"__init__": lambda self, *a, **k: None}))
    module("liblathe.base.boundbox", BoundBox=type("BoundBox", (), {"__init__": lambda self, *a, **k: None}))
    module("liblathe.base.tool", Tool=type("Tool", (), {}))
    module("liblathe.base.refusal", Refusal=type("Refusal", (Exception,), {}))
