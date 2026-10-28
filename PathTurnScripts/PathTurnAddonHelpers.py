# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 Daniel Wood <s.d.wood.82@gmail.com>                *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import importlib.util
import os
import sys


def needs_path(path, sys_path, liblathe_origin):
    """Whether the vendored LibLathe at path must be put first on sys_path: not when it is
    already there or liblathe is already importable from it. The fork's API differs from
    upstream liblathe, so an installed one must not shadow it."""
    norm = os.path.normcase(os.path.abspath(path))
    if liblathe_origin and os.path.normcase(os.path.abspath(liblathe_origin)).startswith(norm + os.sep):
        return False
    return norm not in [os.path.normcase(os.path.abspath(p)) for p in sys_path]


def _liblathe_origin():
    try:
        spec = importlib.util.find_spec("liblathe")
    except (ImportError, ValueError):
        return None
    return spec.origin if spec is not None else None


# the vendored LibLathe (a submodule), ahead of any liblathe installed elsewhere
pathScripts = os.path.dirname(__file__)
__dir__ = os.path.dirname(pathScripts)
liblathePath = os.path.join(__dir__, 'LibLathe')
if needs_path(liblathePath, sys.path, _liblathe_origin()):
    sys.path.insert(0, liblathePath)

from liblathe.base.boundbox import BoundBox
from liblathe.base.point import Point


def getResourcePath(resName):
    # get this directory
    pathScripts = os.path.dirname(__file__)
    # get the parent directory
    __dir__ = os.path.dirname(pathScripts)
    # get the resourse directory
    resourcePath = os.path.join(__dir__, 'Gui/Resources/panels')
    res = os.path.join(resourcePath, resName)

    return res


def getliblatheBoundBox(FcBB):
    liblatheBoundbox = BoundBox(Point(FcBB.XMin, FcBB.YMin, FcBB.ZMin), Point(FcBB.XMax, FcBB.YMax, FcBB.ZMax))
    return liblatheBoundbox
