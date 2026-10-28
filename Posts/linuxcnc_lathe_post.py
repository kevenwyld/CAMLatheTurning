# SPDX-License-Identifier: LGPL-2.1-or-later
"""LinuxCNC lathe post: CAM's LinuxCNC post plus G18 G8 at the start, G33/G76/G96/G97 with
their words formatted for a lathe (see lathe_word), and no up-and-back between operations
(see drop_redundant_rapids). Found by CAM through package.xml."""

import importlib.util
import os
import re

import FreeCAD

from Path.Post.scripts.linuxcnc_post import Linuxcnc


def _load_words():
    """lathe_post_words.py beside this file: CAM loads posts by path, so their folder is not on sys.path."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lathe_post_words.py")
    spec = importlib.util.spec_from_file_location("lathe_post_words", path)
    words = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(words)
    return words


_words = _load_words()
LATHE_WORDS = _words.LATHE_WORDS
drop_redundant_rapids = _words.drop_redundant_rapids
lathe_word = _words.lathe_word
with_lathe_words = _words.with_lathe_words

translate = FreeCAD.Qt.translate

LATHE_MODES = "G18 G8"
# a machine post (CAM's machine editor lists only these; older CAM ignores it)
POST_TYPE = "machine"

EXTRA_COMMANDS = ("G7", "G8", "G18", "G33", "G76", "G96", "G97")


class Linuxcnc_Lathe(Linuxcnc):
    def __init__(self, job, tooltip=None, tooltipargs=None, units="Metric") -> None:
        super().__init__(job=job, tooltip=tooltip or translate("CAM", "LinuxCNC lathe post processor"),
                         tooltipargs=[] if tooltipargs is None else tooltipargs, units=units)

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

