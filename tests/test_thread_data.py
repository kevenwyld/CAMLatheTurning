# SPDX-License-Identifier: LGPL-2.1-or-later
"""ThreadData: the size tables, depths, size checks and tolerance classes."""

import csv
import io

import pytest

from PathTurnScripts import ThreadData

# rows from CAM's Mod/CAM/Data/Threads files, with their headers (the column order differs)
CSV = {
    "6g": "name,pitch,tol,dMajorMax,dMajorMin,dPitchMax,dPitchMin,dMinorMax,dMinorMin\n"
          "M12 x 1.75,1.75,6G,11.966,11.701,10.829,10.679,10.072,9.601\n",
    "6H": "name,pitch,tol,dMinorMin,dMinorMax,dPitchMin,dPitchMax,dMajorMin,dMajorMax\n"
          "M12 x 1.75,1.75,6H,10.106,10.441,10.863,11.063,12,12.452\n",
    "2A": "name,tpi,class,dNominal,dMajorMax,dMajorMin,dPitchMax,dPitchMin,dMinorMax,dMinorMin\n"
          "1/4-20,20,2A,0.2500,0.2489,0.2408,0.2164,0.2127,0.1876,0.1819\n"
          "10-32,32,2A,0.1900,0.1891,0.1831,0.1688,0.1658,0.1508,0.1466\n",
}


@pytest.fixture
def class_tables(monkeypatch):
    tables = {cls: list(csv.DictReader(io.StringIO(text))) for cls, text in CSV.items()}
    monkeypatch.setattr(ThreadData, "_tables", tables)
    return tables


@pytest.mark.parametrize("standard", sorted(ThreadData.TABLES))
def test_every_size_round_trips_through_lookup(standard):
    table = ThreadData.TABLES[standard]
    names = ThreadData.sizes(standard)
    assert names == [name for name, _, _ in table]
    assert len(set(names)) == len(names)
    for name, major, pitch in table:
        assert ThreadData.lookup(standard, name) == (major, pitch)


def test_lookup_of_an_unknown_size_or_standard():
    assert ThreadData.lookup("Metric coarse", "M13") is None
    assert ThreadData.lookup("Custom", "M12") is None
    assert ThreadData.sizes("Custom") == []


def test_unified_sizes_are_converted_to_mm():
    assert ThreadData.lookup("UNC", "1/4-20") == pytest.approx((6.35, 1.27))
    assert ThreadData.lookup("UNF", "#10-32") == pytest.approx((0.19 * 25.4, 25.4 / 32))
    assert ThreadData.lookup("UNF", "#0-80") == pytest.approx((0.06 * 25.4, 25.4 / 80))


def test_depth_and_diameters_of_the_basic_profile():
    assert ThreadData.depth(2.0, False) == pytest.approx(1.22686)
    assert ThreadData.depth(2.0, True) == pytest.approx(1.08254)
    assert ThreadData.start_diameter(12.0, 1.75, False) == 12.0
    assert ThreadData.start_diameter(12.0, 1.75, True) == pytest.approx(12.0 - 1.08253 * 1.75)
    assert ThreadData.target_diameter(12.0, 1.75, True) == 12.0
    assert ThreadData.target_diameter(12.0, 1.75, False) == pytest.approx(12.0 - 2 * 0.61343 * 1.75)


@pytest.mark.parametrize("pitch", [1.0, 1.75, 3.0])
def test_size_problem_external_boundaries(pitch):
    major = 12.0
    allowance = max(0.25, 0.2 * pitch)
    assert ThreadData.size_problem(major, pitch, False, major) is None
    assert ThreadData.size_problem(major, pitch, False, major + 0.01) is None
    assert "larger" in ThreadData.size_problem(major, pitch, False, major + 0.0101)
    assert ThreadData.size_problem(major, pitch, False, major - allowance) is None
    assert "well under" in ThreadData.size_problem(major, pitch, False, major - allowance - 1e-4)


@pytest.mark.parametrize("pitch", [1.0, 1.75, 3.0])
def test_size_problem_internal_boundaries(pitch):
    major = 12.0
    d1 = ThreadData.start_diameter(major, pitch, True)
    allowance = max(0.25, 0.2 * pitch)
    assert ThreadData.size_problem(major, pitch, True, d1) is None
    assert ThreadData.size_problem(major, pitch, True, d1 - 0.01) is None
    assert "smaller" in ThreadData.size_problem(major, pitch, True, d1 - 0.0101)
    assert ThreadData.size_problem(major, pitch, True, d1 + allowance) is None
    assert "well over" in ThreadData.size_problem(major, pitch, True, d1 + allowance + 1e-4)


def test_classes_on_offer():
    assert ThreadData.classes("Metric coarse", False) == ["6g", "4g6g", ThreadData.BASIC]
    assert ThreadData.classes("Metric fine", True) == ["6H", ThreadData.BASIC]
    assert ThreadData.classes("UNC", False) == ["2A", "3A", ThreadData.BASIC]
    assert ThreadData.classes("UNF", True) == ["2B", "3B", ThreadData.BASIC]
    assert ThreadData.classes("Custom", False) == [ThreadData.BASIC]


def test_tolerance_reads_the_class_whatever_its_column_order(class_tables):
    ext = ThreadData.tolerance("Metric coarse", "M12", False, "6g")
    assert ext == {"major_min": 11.701, "major_max": 11.966, "pitch_min": 10.679, "pitch_max": 10.829,
                   "minor_min": 9.601, "minor_max": 10.072}
    internal = ThreadData.tolerance("Metric coarse", "M12", True, "6H")
    assert internal["minor_min"] == 10.106 and internal["major_max"] == 12.452


def test_tolerance_of_a_unified_size_is_in_mm(class_tables):
    tol = ThreadData.tolerance("UNC", "1/4-20", False, "2A")
    assert tol["pitch_min"] == pytest.approx(0.2127 * 25.4)
    assert ThreadData.tolerance("UNF", "#10-32", False, "2A")["major_max"] == pytest.approx(0.1891 * 25.4)


def test_no_tolerance_for_basic_an_unknown_class_or_a_size_without_data(class_tables):
    assert ThreadData.tolerance("Metric coarse", "M12", False, ThreadData.BASIC) is None
    assert ThreadData.tolerance("Metric coarse", "M12", False, "7h") is None
    assert ThreadData.tolerance("Metric coarse", "M10", False, "6g") is None
    assert ThreadData.tolerance("Custom", "M12", False, "6g") is None


def test_class_target_diameter_puts_the_pitch_diameter_mid_range(class_tables):
    major, pitch = 12.0, 1.75
    assert ThreadData.class_target_diameter(major, pitch, False, None) == ThreadData.target_diameter(major, pitch, False)
    tol = ThreadData.tolerance("Metric coarse", "M12", False, "6g")
    shift = (10.679 + 10.829) / 2 - ThreadData.basic_pitch_diameter(major, pitch)
    assert ThreadData.class_target_diameter(major, pitch, False, tol) == pytest.approx(
        ThreadData.target_diameter(major, pitch, False) + shift)
    assert shift < 0     # an external class sits under the basic size
    internal = ThreadData.tolerance("Metric coarse", "M12", True, "6H")
    assert ThreadData.class_target_diameter(major, pitch, True, internal) > major


def test_dimensions_with_and_without_class_data(class_tables):
    tol = ThreadData.tolerance("Metric coarse", "M12", False, "6g")
    values = ThreadData.dimensions(tol, False, 6.0, 1.0)
    assert values["ThreadPitchDiaMin"] == 10.679 and values["ThreadMinorDiaMax"] == 10.072
    assert values[ThreadData.ROOT] == 10.0
    bare = ThreadData.dimensions(None, True, 5.0, 0.9)
    assert all(bare[prop] == 0.0 for prop, _ in ThreadData.DIMENSIONS)
    assert bare[ThreadData.ROOT] == pytest.approx(11.8)
    assert len(values) == 7
