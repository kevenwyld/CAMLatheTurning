# SPDX-License-Identifier: LGPL-2.1-or-later
"""The addon's modules are imported against the stand-ins in fakefreecad (no FreeCAD needed)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for path in (HERE, ROOT, os.path.join(ROOT, "Posts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import fakefreecad  # noqa: E402

fakefreecad.install()
