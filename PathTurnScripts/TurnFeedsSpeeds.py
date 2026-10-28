# SPDX-License-Identifier: LGPL-2.1-or-later
"""Constant surface speed: the surface speed from CAM's feeds & speeds data (the tool's
preset, else the stock material), the max rpm from the Job's machine. No GUI needed."""

import FreeCAD

translate = FreeCAD.Qt.translate

# CAM's Feeds & Speeds (FreeCAD 1.1): without it there is no constant surface speed
try:
    from Path.Tool.FeedsSpeeds import MaterialContext, OpContext, ToolContext, derive_preset_label, get_presets
    from Path.Tool.FeedsSpeeds.providers import MachinabilityProvider, ToolPresetProvider
    available, missing = True, ""
except ImportError as e:
    available, missing = False, str(e)
try:
    # private, only to name the preset a speed came from (no public equivalent; see CONTRACT.md)
    from Path.Tool.FeedsSpeeds.providers import _score_preset
except ImportError:
    _score_preset = None

# CAM's preset op types are milling names; the turning operations use the
# nearest (roughing, finishing, grooving)
OP_TYPE_ROUGHING = "adaptive"
OP_TYPE_FINISHING = "profile"
OP_TYPE_GROOVING = "slot"

# the addon's turning shapes (CAM's shape ids)
TURNING_SHAPES = ("isoshape", "grooving", "fullradius", "threading")


def check_css(enabled):
    """True when the surface speed can be worked out. Without CAM's Feeds & Speeds: False,
    or with constant surface speed switched on, a RuntimeError that says so."""
    if available:
        return True
    if enabled:
        raise RuntimeError(translate("TurnPath", "Constant surface speed needs CAM's Feeds & Speeds, which this "
                                                 "FreeCAD does not have ({}). Turn Constant surface speed off").format(missing))
    return False


def is_turning_tool(tool):
    return (getattr(tool, "ShapeID", "") or "").lower() in TURNING_SHAPES


def _value(quantity, default=None):
    try:
        return float(quantity.Value) if hasattr(quantity, "Value") else float(quantity)
    except (AttributeError, TypeError, ValueError):
        return default


def tool_context(tool, diameter=0.0):
    '''The tool's feeds & speeds data as CAM's resolver takes it: one cutting
    edge (so chipload is feed per revolution).'''
    chipload = _value(getattr(tool, "Chipload", None))
    return ToolContext(diameter=diameter, flutes=1, presets=tuple(get_presets(tool)),
                       shape_id=getattr(tool, "ShapeID", "") or "",
                       tool_material=getattr(tool, "Material", None) or None,
                       chipload_default=chipload if chipload and chipload > 0 else None)


def _m_per_min(props, key):
    raw = props.get(key)
    if not raw:
        return None
    try:
        return float(FreeCAD.Units.Quantity(raw).getValueAs("m/min"))
    except (TypeError, ValueError, AttributeError):
        return None


def material_context(job):
    '''The Job's stock material, with its Machinability surface speeds (m/min).'''
    material = getattr(getattr(job, "Stock", None), "ShapeMaterial", None)
    if material is None:
        return MaterialContext()
    props = getattr(material, "PhysicalProperties", {}) or {}
    return MaterialContext(uuid=getattr(material, "UUID", None) or None, name=getattr(material, "Name", None) or None,
                           surface_speed_hss=_m_per_min(props, "SurfaceSpeedHSS"),
                           surface_speed_carbide=_m_per_min(props, "SurfaceSpeedCarbide"))


def surface_speed(tool, job, op_type):
    '''(surface speed in m/min, where it came from), or (None, why not), in
    the order CAM's resolver takes them: the tool's best-matching preset, then
    the stock material.'''
    tool_ctx, material, op = tool_context(tool), material_context(job), OpContext(op_type=op_type)
    found = ToolPresetProvider().suggest(tool_ctx, material, op)
    if found is not None and found.surface_speed:
        label = ""
        if _score_preset is not None:
            scored = [(_score_preset(p, material, op), p) for p in tool_ctx.presets]
            best = max((s for s in scored if s[0] is not None), key=lambda s: s[0], default=(None, None))[1]
            label = derive_preset_label(best, translate("TurnPath", "unnamed")) if best else ""
        return found.surface_speed, translate("TurnPath", "tool preset {}").format(label).strip()
    found = MachinabilityProvider().suggest(tool_ctx, material, op)
    if found is not None and found.surface_speed:
        return found.surface_speed, translate("TurnPath", "stock material {} ({} tool)").format(
            material.name or "?", tool_ctx.tool_material)
    if material.name is None:
        why = translate("TurnPath", "the tool has no Feeds & Speeds preset with a surface speed and the Job's stock "
                                    "has no material")
    else:
        why = translate("TurnPath", "the tool has no Feeds & Speeds preset with a surface speed for this operation "
                                    "and the stock material ({}), which has none for a {} tool").format(
                                        material.name, tool_ctx.tool_material)
    return None, why


def machine_max_rpm(job):
    '''The first spindle's maximum speed in the Job's machine definition (0: none).'''
    try:
        machine = job.Proxy.getMachine()
    except (AttributeError, TypeError):
        return 0.0
    spindles = (getattr(machine, "spindles", None) or []) if machine is not None else []
    return float(getattr(spindles[0], "max_rpm", 0.0) or 0.0) if spindles else 0.0


def stock_diameter(job):
    '''The stock's turned diameter: twice its furthest extent from the spindle (Z) axis.'''
    stock = getattr(job, "Stock", None)
    shape = getattr(stock, "Shape", None)
    if shape is None or shape.isNull():
        return 0.0
    bb = shape.BoundBox
    return 2.0 * max(abs(bb.XMin), abs(bb.XMax), abs(bb.YMin), abs(bb.YMax))

