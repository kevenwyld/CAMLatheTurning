# SPDX-License-Identifier: LGPL-2.1-or-later
"""The lathe post's text rules, free of FreeCAD so they can be tested: the words it formats
itself (lathe_word) and the rapids it drops between operations (drop_redundant_rapids)."""

import math
import re

# words the post formats itself (for the commands that need it)
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
                # K as CAM prints it (format() rounding, not round())
                k_printed = float(format(k / unit, ".%df" % axis_places))
                return _fixed(math.ceil(k_printed / n ** (1.0 / r) * 1e6 - 1e-6) / 1e6, 6)
        return None
    if command == "G33" and word == "K":
        return _fixed(value / unit, 6)
    if command == "G96" and word == "S":
        return _fixed(value / (0.3048 if imperial else 1.0), 1)
    return None


_LINE_NUMBER = re.compile(r"^N\d+\s*")
_MODAL_ONLY = re.compile(r"^(?:N\d+\s*)?G1[789]$")
_RAPID = re.compile(r"^\s*(?:N\d+\s*)?G0?0\b(?P<words>[^(;]*)$")
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
        # comments (numbered too), and the plane each operation selects, move nothing
        body = _LINE_NUMBER.sub("", stripped)
        if not body or body.startswith("(") or body.startswith(";") or _MODAL_ONLY.match(stripped):
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
    prefix = re.match(r"^(\s*(?:N\d+\s*)?G0?0)", lines[last]).group(1)
    lines[last] = prefix + " X" + x + ((" Z" + z) if z is not None else "")
