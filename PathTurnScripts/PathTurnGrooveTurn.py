# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Turn Groove-Turn: groove turning (also called plunge turning or
multi-directional turning) with a grooving or full radius insert, across the
whole Z range: side-turning passes along the diameters, level by level in
both directions, plunging where the blade has to go down, then the finish
passes along the profile (down walls, across, up walls) from Turn Groove.
It is Turn Groove with Side-turn roughing and the whole part as its range
by default.
"""
import FreeCAD
import PathTurnScripts.PathTurnGroove as PathTurnGroove
import PathTurnScripts.TurnFeedsSpeeds as TurnFeedsSpeeds


class ObjectTurnGrooveTurn(PathTurnGroove.ObjectTurnGroove):
    '''Proxy class for groove-turning operations.'''
    # CAM's feeds & speeds op type (constant surface speed)
    css_op_type = TurnFeedsSpeeds.OP_TYPE_ROUGHING

    default_strategy = "Side-turn"


def SetupProperties():
    return PathTurnGroove.SetupProperties()


def Create(name, obj=None, parentJob=None):
    '''Create(name) ... Creates and returns a Turn Groove-Turn operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTurnGrooveTurn(obj, name, parentJob)
    return obj
