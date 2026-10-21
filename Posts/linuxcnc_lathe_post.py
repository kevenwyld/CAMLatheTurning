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
- No up-and-back between operations: each operation ends at the safe
  position and the next starts from it, so consecutive rapids along Z at
  the same safe X, with only comments between them, are reduced to the
  first and the last.

Found by CAM through the <postprocessor> entry in the addon's package.xml.
"""

import re

import FreeCAD
import Path

from Path.Post.scripts.linuxcnc_post import Linuxcnc

translate = FreeCAD.Qt.translate

LATHE_MODES = "G18 G8"
EXTRA_COMMANDS = ("G7", "G8", "G18", "G33", "G76")


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
