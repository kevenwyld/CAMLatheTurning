# SPDX-License-Identifier: LGPL-2.1-or-later
"""
LinuxCNC lathe post processor for the Turning Addon.

CAM's LinuxCNC post, with what a lathe program needs:

- G18 G8 at the start (the XZ plane, radius mode): the turning operations
  program X as a radius, and many LinuxCNC lathe configurations start in
  diameter mode (G7), so the program states it rather than relying on the
  machine's startup code.
- G33 (spindle-synchronized motion) and G76 (threading cycle) accepted, and
  G76's Q word (the infeed angle) kept: CAM's LinuxCNC post writes Q only
  for G10, G64, G73 and G83, which made a G76 infeed radially.
- G76: J (first pass depth) worked out from K as printed, with six
  decimals, so LinuxCNC's pass loop makes exactly the passes the path
  meant (a J rounded down added one a micron short of K); P (pitch)
  converted for G20, R (degression) not.
- G33's K and G76's P (pitches) with six decimals.
- G96 / G97 (constant surface speed) accepted, G96's S (the surface speed,
  m/min in the path) written in ft/min for an inch program (G20), as G96
  takes it there, and its D (the maximum spindle speed) in rpm.
- No up-and-back between operations: each operation ends at the safe
  position and the next starts from it, so consecutive rapids along Z at
  the same safe X, with only comments between them, are reduced to the
  first and the last.

Found by CAM through the <postprocessor> entry in the addon's package.xml.
"""

import math
import re

import FreeCAD
import Path

from Path.Post.scripts.linuxcnc_post import Linuxcnc

translate = FreeCAD.Qt.translate

LATHE_MODES = "G18 G8"
EXTRA_COMMANDS = ("G7", "G8", "G18", "G33", "G76", "G96", "G97")


class Linuxcnc_Lathe(Linuxcnc):
    def __init__(self, job, tooltip=None, tooltipargs=[], units="Metric") -> None:
        super().__init__(job=job, tooltip=tooltip or translate("CAM", "LinuxCNC lathe post processor"),
                         tooltipargs=tooltipargs, units=units)

    def init_values(self, values) -> None:
        super().init_values(values)
        values["POSTPROCESSOR_FILE_NAME"] = __name__
        # G33 / G76 among the commands this machine takes
        supported = values.get("SUPPORTED_COMMANDS")
        if isinstance(supported, str) and supported:
            names = supported.split("\n")
            values["SUPPORTED_COMMANDS"] = "\n".join(names + [c for c in EXTRA_COMMANDS if c not in names])
        # keep G76's Q (the infeed angle, degrees)
        functions = values.get("PARAMETER_FUNCTIONS")
        if isinstance(functions, dict) and "Q" in functions:
            cam_q = functions["Q"]

            def q_parameter(values, command, param, value, parameters, location):
                if command == "G76":
                    return ("%.4f" % float(value)).rstrip("0").rstrip(".")
                return cam_q(values, command, param, value, parameters, location)

            functions["Q"] = q_parameter
        # Threading words that CAM's generic formatting gets wrong for G33/G76
        if isinstance(functions, dict):
            def unit(values):
                return 25.4 if values.get("UNITS") == "G20" else 1.0

            def fixed(number, places):
                return format(number, ".%df" % places).rstrip("0").rstrip(".")

            def wrap(word, handler):
                cam = functions.get(word)

                def parameter(values, command, param, value, parameters, location):
                    done = handler(values, command, value, parameters, location, cam)
                    if done is not None:
                        return done
                    if cam is not None:
                        return cam(values, command, param, value, parameters, location)
                    return format(float(value), ".%df" % int(values.get("AXIS_PRECISION", 3)))

                functions[word] = parameter

            # a pitch (G33's K, G76's P) is a length per turn: converted for G20,
            # and with more decimals than a position, its error adding up over
            # every turn of the thread
            def g33_pitch(values, command, value, parameters, location, cam):
                return fixed(float(value) / unit(values), 6) if command == "G33" else None

            def g76_pitch(values, command, value, parameters, location, cam):
                return fixed(float(value) / unit(values), 6) if command == "G76" else None

            def g76_degression(values, command, value, parameters, location, cam):
                return fixed(float(value), 4) if command == "G76" else None

            wrap("K", g33_pitch)
            wrap("P", g76_pitch)
            # G76's R is the degression: a ratio, not a length (not converted)
            wrap("R", g76_degression)

            # G76's J (the first pass's depth): LinuxCNC cuts at J*k^(1/R) for
            # k = 1, 2, ... while that is below K, then once at K. With J and K
            # printed rounded, the pass count could change (J rounded down added
            # a pass a micron short of K; rounded up at a coarse precision, or
            # with K rounded down, it could lose one). So J is worked out from K
            # as printed: the n-th pass (n the pass the path meant to reach K
            # with) reaches it and the one before stays short, J printed with
            # six decimals and rounded up.
            def first_depth(values, command, value, parameters, location, cam_j):
                if command != "G76" or "K" not in parameters:
                    return None
                j, k = float(value), float(parameters["K"])
                r = max(float(parameters.get("R", 1.0)) or 1.0, 1.0)
                if j <= 0 or k <= 0:
                    return None
                n = max(1, int(round((k / j) ** r)))
                k_scale = 10 ** int(values.get("AXIS_PRECISION", 3))
                k_printed = round(k / unit(values) * k_scale) / k_scale
                return fixed(math.ceil(k_printed / n ** (1.0 / r) * 1e6 - 1e-6) / 1e6, 6)

            wrap("J", first_depth)
        # G96's S is a surface speed: m/min in the path, ft/min for G20
        if isinstance(functions, dict) and "S" in functions:
            cam_s = functions["S"]

            def s_parameter(values, command, param, value, parameters, location):
                if command == "G96":
                    speed = float(value) / (0.3048 if values.get("UNITS") == "G20" else 1.0)
                    return ("%.1f" % speed).rstrip("0").rstrip(".")
                return cam_s(values, command, param, value, parameters, location)

            functions["S"] = s_parameter

    def _lathe_preamble(self):
        """The lathe's plane and radius mode at the start of the preamble; a
        G17 in the machine's preamble would select the wrong plane."""
        preamble = self.values.get("PREAMBLE") or ""
        preamble = re.sub(r"\bG17\b", "G18", preamble)
        if not re.search(r"\bG8\b", preamble):
            preamble = LATHE_MODES + ("\n" + preamble if preamble else "")
        self.values["PREAMBLE"] = preamble

    # CAM writes the preamble on one of two paths, depending on the version:
    # the sections (UtilsExport) or the postables' prefix
    def process_postables(self):
        self._lathe_preamble()
        return super().process_postables()

    def _expand_prefix(self, postables):
        self._lathe_preamble()
        super()._expand_prefix(postables)

    def export(self):
        sections = super().export()
        if not sections:
            return sections
        return [(name, drop_redundant_rapids(text) if isinstance(text, str) else text) for name, text in sections]

    @property
    def tooltip(self):
        return translate("CAM", "LinuxCNC lathe post processor: G18 G8 (radius mode), G33 and G76 threading, "
                                "G96 constant surface speed, "
                                "no up-and-back between operations")


_MODAL_ONLY = re.compile(r"^(?:N\d+\s+)?G1[789]$")
_RAPID = re.compile(r"^\s*(?:N\d+\s+)?G0?0\b(?P<words>[^(;]*)$")
_WORD = re.compile(r"([XYZ])\s*(-?\d+(?:\.\d*)?)")


def _rapid_words(line):
    m = _RAPID.match(line)
    if not m:
        return None
    words = dict(_WORD.findall(m.group("words")))
    other = re.sub(r"[XYZ]\s*-?\d+(?:\.\d*)?|F\s*-?\d+(?:\.\d*)?", "", m.group("words")).strip()
    return None if other else words


def drop_redundant_rapids(text):
    """
    Within a run of rapids (G0) at the same X, with only comments and blank
    lines between them, keep the first (out to that X where the tool is) and
    the last: between them the tool only travels along Z at that X, so going
    straight from the first to the last drops the detours (an operation's
    exit to the safe Z and the next operation's return from it). Comments
    and plane selections (G17-G19) between them move nothing; anything else
    (a feed move, a tool change, spindle or coolant) ends the run.
    """
    lines = text.split("\n")
    keep = [True] * len(lines)
    run = []           # indexes of the rapids in the current run
    run_x = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # comments, and the plane each operation selects, move nothing
        if not stripped or stripped.startswith("(") or stripped.startswith(";") or _MODAL_ONLY.match(stripped):
            continue
        words = _rapid_words(line)
        x = words.get("X") if words else None
        if words is not None and x is not None and (run_x is None or float(x) == float(run_x)) and "Y" not in words:
            run.append(i)
            run_x = x
            continue
        if words is not None and x is None and run and "Y" not in words:
            run.append(i)          # a Z-only rapid at the run's X
            continue
        _close(run, lines, keep)
        run, run_x = ([i], x) if (words is not None and x is not None and "Y" not in words) else ([], None)
    _close(run, lines, keep)
    return "\n".join(line for line, k in zip(lines, keep) if k)


def _close(run, lines, keep):
    """
    Keep the run's first rapid (it takes the tool out to the run's X at the
    Z it was at, e.g. out of the cut) and its last; the moves between are
    along Z at that X, so going from the first straight to the last covers
    no ground they did not.
    """
    if len(run) < 3:
        return
    z = None
    for i in run[1:]:
        z = _rapid_words(lines[i]).get("Z", z)
    for i in run[1:-1]:
        keep[i] = False
    last = run[-1]
    x = _rapid_words(lines[run[0]]).get("X")
    prefix = re.match(r"^(\s*(?:N\d+\s+)?G0?0)", lines[last]).group(1)
    lines[last] = prefix + " X" + x + ((" Z" + z) if z is not None else "")
