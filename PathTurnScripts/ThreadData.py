# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Standard threads for Turn Thread: ISO metric coarse and fine (ISO 261) and
Unified coarse and fine (UNC, UNF), as major diameter and pitch in mm.

All four use the 60 degree basic profile (ISO 68-1 / ASME B1.1), with
fundamental triangle height H = 0.866025 P:

  external thread depth  h3 = 17/24 H = 0.61343 P  (from the major diameter)
  internal thread depth  H1 =  5/8 H  = 0.54127 P  (from the minor diameter)
  internal minor diameter   D1 = D - 1.08253 P

The depths are to the theoretical sharp point of the threading insert,
which is where Turn Thread programs it.
"""

EXTERNAL_DEPTH = 0.61343
INTERNAL_DEPTH = 0.54127
MINOR_OFFSET = 1.08253

STANDARDS = ("Metric coarse", "Metric fine", "UNC", "UNF", "Custom")

_METRIC_COARSE = (
    ("M1", 1.0, 0.25), ("M1.2", 1.2, 0.25), ("M1.4", 1.4, 0.3), ("M1.6", 1.6, 0.35), ("M2", 2.0, 0.4),
    ("M2.5", 2.5, 0.45), ("M3", 3.0, 0.5), ("M3.5", 3.5, 0.6), ("M4", 4.0, 0.7), ("M5", 5.0, 0.8),
    ("M6", 6.0, 1.0), ("M8", 8.0, 1.25), ("M10", 10.0, 1.5), ("M12", 12.0, 1.75), ("M14", 14.0, 2.0),
    ("M16", 16.0, 2.0), ("M18", 18.0, 2.5), ("M20", 20.0, 2.5), ("M22", 22.0, 2.5), ("M24", 24.0, 3.0),
    ("M27", 27.0, 3.0), ("M30", 30.0, 3.5), ("M33", 33.0, 3.5), ("M36", 36.0, 4.0), ("M39", 39.0, 4.0),
    ("M42", 42.0, 4.5), ("M45", 45.0, 4.5), ("M48", 48.0, 5.0), ("M52", 52.0, 5.0), ("M56", 56.0, 5.5),
    ("M60", 60.0, 5.5), ("M64", 64.0, 6.0),
)

_METRIC_FINE = (
    ("M8x1", 8.0, 1.0), ("M10x1", 10.0, 1.0), ("M10x1.25", 10.0, 1.25), ("M12x1", 12.0, 1.0),
    ("M12x1.25", 12.0, 1.25), ("M12x1.5", 12.0, 1.5), ("M14x1.5", 14.0, 1.5), ("M16x1.5", 16.0, 1.5),
    ("M18x1.5", 18.0, 1.5), ("M18x2", 18.0, 2.0), ("M20x1.5", 20.0, 1.5), ("M20x2", 20.0, 2.0),
    ("M22x1.5", 22.0, 1.5), ("M22x2", 22.0, 2.0), ("M24x1.5", 24.0, 1.5), ("M24x2", 24.0, 2.0),
    ("M27x2", 27.0, 2.0), ("M30x2", 30.0, 2.0), ("M33x2", 33.0, 2.0), ("M36x3", 36.0, 3.0),
    ("M39x3", 39.0, 3.0), ("M42x3", 42.0, 3.0), ("M45x3", 45.0, 3.0), ("M48x3", 48.0, 3.0),
)

INCH = 25.4


def _numbered(n):
    """Major diameter in inches of a numbered Unified size (#0 .. #12)."""
    return 0.060 + 0.013 * n


_UNC_INCH = (
    ("#1-64", _numbered(1), 64), ("#2-56", _numbered(2), 56), ("#3-48", _numbered(3), 48),
    ("#4-40", _numbered(4), 40), ("#5-40", _numbered(5), 40), ("#6-32", _numbered(6), 32),
    ("#8-32", _numbered(8), 32), ("#10-24", _numbered(10), 24), ("#12-24", _numbered(12), 24),
    ("1/4-20", 0.25, 20), ("5/16-18", 0.3125, 18), ("3/8-16", 0.375, 16), ("7/16-14", 0.4375, 14),
    ("1/2-13", 0.5, 13), ("9/16-12", 0.5625, 12), ("5/8-11", 0.625, 11), ("3/4-10", 0.75, 10),
    ("7/8-9", 0.875, 9), ("1-8", 1.0, 8), ("1-1/8-7", 1.125, 7), ("1-1/4-7", 1.25, 7),
    ("1-3/8-6", 1.375, 6), ("1-1/2-6", 1.5, 6), ("1-3/4-5", 1.75, 5), ("2-4.5", 2.0, 4.5),
)

_UNF_INCH = (
    ("#0-80", _numbered(0), 80), ("#1-72", _numbered(1), 72), ("#2-64", _numbered(2), 64),
    ("#3-56", _numbered(3), 56), ("#4-48", _numbered(4), 48), ("#5-44", _numbered(5), 44),
    ("#6-40", _numbered(6), 40), ("#8-36", _numbered(8), 36), ("#10-32", _numbered(10), 32),
    ("#12-28", _numbered(12), 28), ("1/4-28", 0.25, 28), ("5/16-24", 0.3125, 24), ("3/8-24", 0.375, 24),
    ("7/16-20", 0.4375, 20), ("1/2-20", 0.5, 20), ("9/16-18", 0.5625, 18), ("5/8-18", 0.625, 18),
    ("3/4-16", 0.75, 16), ("7/8-14", 0.875, 14), ("1-12", 1.0, 12), ("1-1/8-12", 1.125, 12),
    ("1-1/4-12", 1.25, 12), ("1-3/8-12", 1.375, 12), ("1-1/2-12", 1.5, 12),
)


def _unified(table):
    return tuple((name, d * INCH, INCH / tpi) for name, d, tpi in table)


TABLES = {
    "Metric coarse": _METRIC_COARSE,
    "Metric fine": _METRIC_FINE,
    "UNC": _unified(_UNC_INCH),
    "UNF": _unified(_UNF_INCH),
}


def sizes(standard):
    """Size names of a standard, in table order."""
    return [name for name, _, _ in TABLES.get(standard, ())]


def lookup(standard, size):
    """(major diameter, pitch) in mm of a standard size, or None."""
    for name, d, p in TABLES.get(standard, ()):
        if name == size:
            return d, p
    return None


def depth(pitch, internal):
    """Radial thread depth for the 60 degree basic profile."""
    return (INTERNAL_DEPTH if internal else EXTERNAL_DEPTH) * pitch


def start_diameter(major, pitch, internal):
    """The diameter the thread is cut from: the major (external) or the minor (internal)."""
    return major - MINOR_OFFSET * pitch if internal else major


def target_diameter(major, pitch, internal):
    """
    The diameter the thread is cut to, fixed by the standard whatever the
    crests were turned to: the minor diameter d3 = d - 2 * h3 of an
    external thread, the major diameter D of an internal one.
    """
    return major if internal else major - 2 * EXTERNAL_DEPTH * pitch


def size_problem(major, pitch, internal, diameter):
    """
    A short description of how a selected diameter does not fit the size,
    or None. External threads are turned to the major diameter or a little
    under it (e.g. 11.701-11.966 for M12x1.75 6g); internal ones bored to
    the minor diameter or a little over it.
    """
    allowance = max(0.25, 0.2 * pitch)
    if internal:
        d1 = start_diameter(major, pitch, True)
        if diameter < d1 - 0.01:
            return "smaller than the {:.3f} minor diameter".format(d1)
        if diameter > d1 + allowance:
            return "well over the {:.3f} minor diameter".format(d1)
        return None
    if diameter > major + 0.01:
        return "larger than the {:.3f} major diameter".format(major)
    if diameter < major - allowance:
        return "well under the {:.3f} major diameter".format(major)
    return None


# ---------------------------------------------------------------------------
# Tolerance classes, from the tables CAM ships for Thread Milling
# (Mod/CAM/Data/Threads): crest, pitch and minor diameter ranges per size.

BASIC = "Basic (no tolerance)"
_CLASSES = {  # (internal, unified): classes, the first the default
    (False, False): ("6g", "4g6g"),
    (True, False): ("6H",),
    (False, True): ("2A", "3A"),
    (True, True): ("2B", "3B"),
}
_FILES = {"6g": "metric-external-6G.csv", "4g6g": "metric-external-4G6G.csv", "6H": "metric-internal-6H.csv",
          "2A": "imperial-external-2A.csv", "3A": "imperial-external-3A.csv",
          "2B": "imperial-internal-2B.csv", "3B": "imperial-internal-3B.csv"}
_tables = {}


def _unified(standard):
    return standard in ("UNC", "UNF")


def classes(standard, internal):
    """The tolerance classes on offer for a standard, the default first."""
    if not (standard.startswith("Metric") or _unified(standard)):
        return [BASIC]
    return list(_CLASSES[(bool(internal), _unified(standard))]) + [BASIC]


def _table(cls):
    if cls not in _tables:
        import csv
        import os
        rows = []
        try:
            import FreeCAD
            path = os.path.join(FreeCAD.getHomePath(), "Mod", "CAM", "Data", "Threads", _FILES[cls])
            with open(path, newline="") as fp:
                rows = list(csv.DictReader(fp))
        except Exception:
            rows = []
        _tables[cls] = rows
    return _tables[cls]


def tolerance(standard, size, internal, cls):
    """
    The class's diameter ranges for a size, in mm, or None (no class, or the
    size is not in CAM's tables): major_min/max, pitch_min/max, minor_min/max.
    For external threads CAM's minor diameters are the basic profile's flat
    root (d1 based), not the root an insert cuts (d3); they are not used
    for the root.
    """
    if cls == BASIC or cls not in _FILES:
        return None
    found = lookup(standard, size)
    if found is None:
        return None
    major, pitch = found
    for row in _table(cls):
        if _unified(standard):
            if row.get("name") != size.lstrip("#"):
                continue
            scale = 25.4
        else:
            try:
                d, p = row["name"].replace("M", "").split(" x ")
            except (KeyError, ValueError):
                continue
            if abs(float(d) - major) > 1e-6 or abs(float(p) - pitch) > 1e-6:
                continue
            scale = 1.0
        try:
            return {k: float(row[c]) * scale for k, c in (
                ("major_min", "dMajorMin"), ("major_max", "dMajorMax"), ("pitch_min", "dPitchMin"),
                ("pitch_max", "dPitchMax"), ("minor_min", "dMinorMin"), ("minor_max", "dMinorMax"))}
        except (KeyError, ValueError):
            return None
    return None


def basic_pitch_diameter(major, pitch):
    """The basic pitch diameter, d2 = d - 0.649519 P."""
    return major - 0.649519 * pitch


def class_target_diameter(major, pitch, internal, tol):
    """
    The diameter to cut to so the pitch diameter lands in the middle of the
    class's range: for a V profile the pitch diameter moves with the root,
    one for one. Without class data, the basic profile's.
    """
    basic = target_diameter(major, pitch, internal)
    if tol is None:
        return basic
    shift = (tol["pitch_min"] + tol["pitch_max"]) / 2 - basic_pitch_diameter(major, pitch)
    return basic + shift


def best_wire(pitch):
    """Best-size wire diameter for a 60 degree thread, and the term to add to
    the pitch diameter for the measurement over three wires: M = d2 + 3w - 0.866025 P."""
    w = 0.57735 * pitch
    return w, 3 * w - 0.866025 * pitch
