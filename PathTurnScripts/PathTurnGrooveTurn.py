# SPDX-License-Identifier: LGPL-2.1-or-later
"""Turn Groove-Turn: groove (plunge) turning along the whole profile with a grooving or
full radius insert. Turn Groove with Side-turn roughing and the whole part as its range."""
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
