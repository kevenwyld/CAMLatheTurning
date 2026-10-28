# SPDX-License-Identifier: LGPL-2.1-or-later
"""LinuxCNC lathe post: CAM's LinuxCNC post plus G18 G8 at the start, G33/G76/G96/G97 with
their words formatted for a lathe (see lathe_word), and no up-and-back between operations
(see drop_redundant_rapids). Found by CAM through package.xml."""

import math
import re

import FreeCAD
import Path

from Path.Post.scripts.linuxcnc_post import Linuxcnc

translate = FreeCAD.Qt.translate

LATHE_MODES = "G18 G8"
# a machine post (CAM's machine editor lists only these; older CAM ignores it)
POST_TYPE = "machine"

EXTRA_COMMANDS = ("G7", "G8", "G18", "G33", "G76", "G96", "G97")


# words this post formats itself (for the commands that need it)
LATHE_WORDS = ("E", "J", "K", "P", "Q", "R", "S")


def with_lathe_words(order):
    """CAM's parameter order with E (G76's taper length) added after L: a
    word not in the order is not written."""
    order = order or "XYZABCUVWFSIJKTQRPDHL"
    return order if "E" in order else order + "E"


def _fixed(number, places):
    return format(number, ".%df" % places).rstrip("0").rstrip(".")


def lathe_word(word, value, command, params, imperial, axis_places):
    """A word's text as this post writes it, or None for CAM's formatting: G76's E/P as lengths
    (P six decimals), J from K as printed so LinuxCNC makes exactly the passes meant, Q/R not
    converted; G33's K six decimals; G96's S in ft/min for an inch program."""
    unit = 25.4 if imperial else 1.0
    value = float(value)
    if command == "G76":
        if word in ("Q", "R"):
            return _fixed(value, 4)
        if word == "P":
            return _fixed(value / unit, 6)
        if word == "E":
            return format(value / unit, ".%df" % axis_places)
        if word == "J" and "K" in params:
            k = float(params["K"])
            r = max(float(params.get("R", 1.0)) or 1.0, 1.0)
            if value > 0 and k > 0:
                n = max(1, int(round((k / value) ** r)))
                scale = 10 ** axis_places
                k_printed = round(k / unit * scale) / scale
                return _fixed(math.ceil(k_printed / n ** (1.0 / r) * 1e6 - 1e-6) / 1e6, 6)
        return None
    if command == "G33" and word == "K":
        return _fixed(value / unit, 6)
    if command == "G96" and word == "S":
        return _fixed(value / (0.3048 if imperial else 1.0), 1)
    return None


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
        # the words the lathe needs, in CAM's order: E (G76's taper length) is
        # missing from it, and CAM drops any word not in the order
        values["PARAMETER_ORDER"] = with_lathe_words(values.get("PARAMETER_ORDER"))
        # the threading and CSS words, on the post's older path (UtilsParse);
        # the machine-based path formats in format_parameter() below
        functions = values.get("PARAMETER_FUNCTIONS")
        if isinstance(functions, dict):
            for word in LATHE_WORDS:
                cam = functions.get(word)

                def parameter(values, command, param, value, parameters, location, cam=cam):
                    text = lathe_word(param, value, command, parameters,
                                      values.get("UNITS") == "G20", int(values.get("AXIS_PRECISION", 3)))
                    if text is not None:
                        return text
                    if cam is not None:
                        return cam(values, command, param, value, parameters, location)
                    return format(float(value), ".%df" % int(values.get("AXIS_PRECISION", 3)))

                functions[word] = parameter

    # --- the machine-based path (CAM's Processor) --------------------------
    def _imperial(self):
        units = self.values.get("OUTPUT_UNITS")
        return self.values.get("UNITS") == "G20" or getattr(units, "name", str(units)).upper().endswith("IMPERIAL")

    def _convert_move(self, command):
        # the machine's configuration sets the parameter order after this
        # post's own values: E (G76's taper length) put back where it is read
        self.values["PARAMETER_ORDER"] = with_lathe_words(self.values.get("PARAMETER_ORDER"))
        # the command's other words, for J (worked out from K and R)
        self._lathe_command = command
        try:
            return super()._convert_move(command)
        finally:
            self._lathe_command = None

    def format_parameter(self, param_name, value, command_name=None):
        if param_name in LATHE_WORDS and command_name:
            command = getattr(self, "_lathe_command", None)
            params = dict(command.Parameters) if command is not None else {}
            text = lathe_word(param_name, value, command_name, params, self._imperial(),
                              int(self.values.get("AXIS_PRECISION", 3)))
            if text is not None:
                return text
        return super().format_parameter(param_name, value, command_name)

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
        # a machine's (or a job's) Generated Parameter Order may lack E
        self.values["PARAMETER_ORDER"] = with_lathe_words(self.values.get("PARAMETER_ORDER"))
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
        return translate("CAM", "LinuxCNC lathe post: G18 G8 radius mode, G33 and G76 threading, "
                                "G96 constant surface speed, no up-and-back between operations")


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
    """In a run of rapids at the same X (only comments and G17-G19 between them), keep the
    first and the last: the tool only travels along Z between them. Anything else ends the run."""
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
    """Keep the run's first rapid (out to its X) and its last; drop the moves between."""
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
