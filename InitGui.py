"""
Path Turning Addon module for FreeCAD.
This file is a standard FreeCAD Addon file
it exists to load the addon data.
"""

import os

import PathTurnScripts

# the LibLathe submodule is not fetched by a plain clone or the Addon Manager's zip download
_addon = os.path.dirname(os.path.dirname(os.path.abspath(PathTurnScripts.__file__)))
if os.path.isfile(os.path.join(_addon, "LibLathe", "liblathe", "__init__.py")):
    import InitTurningAddon  # noqa: F401
else:
    import FreeCAD
    FreeCAD.Console.PrintError("CAM Lathe Turning: LibLathe is missing; run 'git submodule update --init' "
                               "in {}\n".format(_addon))
