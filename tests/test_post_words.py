# SPDX-License-Identifier: LGPL-2.1-or-later
"""The lathe post's text rules (Posts/lathe_post_words.py)."""

import pytest

from lathe_post_words import drop_redundant_rapids, lathe_word, with_lathe_words


def linuxcnc_passes(j, k, r):
    """Passes LinuxCNC's G76 makes: J * n^(1/R) per pass until K is reached."""
    n = 1
    while j * n ** (1.0 / r) < k - 1e-12:
        n += 1
    return n


def cam_k(k_mm, imperial, places):
    """K as CAM's posts print it."""
    return float(format(k_mm / (25.4 if imperial else 1.0), ".%df" % places))


# --- with_lathe_words ---------------------------------------------------------

def test_with_lathe_words_adds_e_once():
    assert with_lathe_words("XYZFIJKPQRL") == "XYZFIJKPQRLE"
    assert with_lathe_words("XYZE") == "XYZE"
    assert with_lathe_words(None).endswith("LE")
    assert with_lathe_words("") == with_lathe_words(None)


# --- lathe_word: G76 J from K -------------------------------------------------

@pytest.mark.parametrize("k, j, r, imperial, places", [
    (0.92, 0.2, 1.5, False, 3),      # M1.5-ish, metric
    (1.0735, 0.15, 2.0, False, 3),   # constant area
    (0.7973, 0.1, 1.0, False, 3),    # constant depth
    (0.92, 0.2, 1.5, True, 4),       # the same in an inch program
    (0.57785, 0.1, 1.5, True, 4),    # K whose printed value round() would get wrong
    (0.74295, 0.1, 1.5, True, 4),
    (0.17145, 0.03, 2.0, True, 4),
    (1.3, 0.0425, 1.5, False, 3),    # many passes
])
def test_g76_j_gives_linuxcnc_the_passes_meant(k, j, r, imperial, places):
    n = max(1, int(round((k / j) ** r)))
    text = lathe_word("J", j, "G76", {"K": k, "R": r}, imperial, places)
    assert linuxcnc_passes(float(text), cam_k(k, imperial, places), r) == n


def test_g76_j_without_r_is_constant_depth_and_r_below_1_counts_as_1():
    one = lathe_word("J", 0.25, "G76", {"K": 1.0}, False, 3)
    assert one == "0.25"
    assert lathe_word("J", 0.25, "G76", {"K": 1.0, "R": 0.5}, False, 3) == one


def test_g76_j_larger_than_k_is_one_pass_at_k():
    assert lathe_word("J", 2.0, "G76", {"K": 0.5, "R": 1.5}, False, 3) == "0.5"


def test_g76_j_left_to_cam_without_k_or_with_zero():
    assert lathe_word("J", 0.2, "G76", {}, False, 3) is None
    assert lathe_word("J", 0.0, "G76", {"K": 1.0}, False, 3) is None
    assert lathe_word("J", 0.2, "G76", {"K": 0.0}, False, 3) is None


# --- lathe_word: P, E, Q, R, G33 K, G96 S --------------------------------------

def test_g76_p_is_the_pitch_as_a_length():
    assert lathe_word("P", 1.5, "G76", {}, False, 3) == "1.5"
    assert lathe_word("P", 25.4 / 20, "G76", {}, True, 4) == "0.05"
    assert lathe_word("P", 25.4 / 13, "G76", {}, True, 4) == "0.076923"


def test_g76_e_is_a_length_at_axis_precision():
    assert lathe_word("E", 1.5, "G76", {}, False, 3) == "1.500"
    assert lathe_word("E", 1.27, "G76", {}, True, 4) == "0.0500"


def test_g76_q_and_r_are_not_converted():
    assert lathe_word("Q", 29.5, "G76", {}, True, 4) == "29.5"
    assert lathe_word("R", 1.5, "G76", {}, True, 4) == "1.5"


def test_g33_k_is_the_pitch_with_six_decimals():
    assert lathe_word("K", 1.25, "G33", {}, False, 3) == "1.25"
    assert lathe_word("K", 25.4 / 13, "G33", {}, True, 4) == "0.076923"


def test_g96_s_is_m_per_min_or_ft_per_min():
    assert lathe_word("S", 200.0, "G96", {}, False, 3) == "200"
    assert lathe_word("S", 200.0, "G96", {}, True, 4) == "656.2"


def test_other_words_and_commands_are_left_to_cam():
    assert lathe_word("S", 1200, "M3", {}, False, 3) is None
    assert lathe_word("Q", 2.0, "G83", {}, False, 3) is None
    assert lathe_word("K", 1.0, "G76", {}, False, 3) is None
    assert lathe_word("K", 1.0, "G2", {}, False, 3) is None


# --- drop_redundant_rapids ----------------------------------------------------

# the end of one operation and the start of the next, as liblathe writes them:
# safe_end (out in X, then to the safe Z) and safe_start (safe X, then along Z)
BETWEEN_OPS = """G1 X10.000 Z-20.000 F100.000
G0 X13.000
G0 X13.000 Z53.000
(Turn Profile)
G18
G0 X13.000
G0 X13.000 Z2.000
G1 X10.000 Z2.000 F100.000"""


def test_the_up_and_back_between_two_ops_is_dropped():
    assert drop_redundant_rapids(BETWEEN_OPS).split("\n") == [
        "G1 X10.000 Z-20.000 F100.000",
        "G0 X13.000",
        "(Turn Profile)",
        "G18",
        "G0 X13.000 Z2.000",
        "G1 X10.000 Z2.000 F100.000"]


def test_numbered_lines_and_numbered_comments():
    text = "\n".join("N%d %s" % (10 * (i + 1), line) for i, line in enumerate(BETWEEN_OPS.split("\n")))
    assert drop_redundant_rapids(text).split("\n") == [
        "N10 G1 X10.000 Z-20.000 F100.000",
        "N20 G0 X13.000",
        "N40 (Turn Profile)",
        "N50 G18",
        "N70 G0 X13.000 Z2.000",
        "N80 G1 X10.000 Z2.000 F100.000"]


def test_g00_spelling():
    out = drop_redundant_rapids(BETWEEN_OPS.replace("G0 ", "G00 "))
    assert out.split("\n")[1:5] == ["G00 X13.000", "(Turn Profile)", "G18", "G00 X13.000 Z2.000"]


def test_semicolon_comments_and_blank_lines_are_skipped():
    out = drop_redundant_rapids(BETWEEN_OPS.replace("(Turn Profile)", "; Turn Profile\n"))
    assert "G0 X13.000 Z53.000" not in out
    assert "; Turn Profile" in out


@pytest.mark.parametrize("between", ["G1 X13.000 Z53.000 F200.000", "M6 T2", "M3 S1200", "G96 S200 D3000", "M8"])
def test_a_feed_tool_change_spindle_or_coolant_command_ends_the_run(between):
    text = BETWEEN_OPS.replace("(Turn Profile)", between)
    assert drop_redundant_rapids(text) == text


def test_a_rapid_with_y_is_not_part_of_a_run():
    text = BETWEEN_OPS.replace("G0 X13.000 Z53.000", "G0 X13.000 Y0.000 Z53.000")
    assert drop_redundant_rapids(text) == text


def test_a_rapid_at_another_x_ends_the_run():
    text = BETWEEN_OPS.replace("(Turn Profile)\nG18\nG0 X13.000\nG0 X13.000 Z2.000",
                               "(Turn Profile)\nG18\nG0 X14.000\nG0 X14.000 Z2.000")
    assert drop_redundant_rapids(text) == text


def test_a_run_of_two_rapids_is_left_alone():
    text = "G1 X10 Z0 F100\nG0 X13\nG0 X13 Z50\nM5"
    assert drop_redundant_rapids(text) == text


def test_z_only_rapids_join_the_run_and_the_last_z_is_kept():
    text = "G1 X10 Z0 F100\nG0 X13\nG0 Z50\nG0 Z20\nG1 X10 F100"
    assert drop_redundant_rapids(text) == "G1 X10 Z0 F100\nG0 X13\nG0 X13 Z20\nG1 X10 F100"


def test_inch_output():
    text = BETWEEN_OPS.replace("13.000", "0.5118").replace("53.000", "2.0866").replace("2.000", "0.0787")
    out = drop_redundant_rapids(text).split("\n")
    assert out[1] == "G0 X0.5118" and out[4] == "G0 X0.5118 Z0.0787"
    assert len(out) == 6


def test_a_rapid_with_a_trailing_comment_ends_the_run():
    text = BETWEEN_OPS.replace("G0 X13.000 Z53.000", "G0 X13.000 Z53.000 (safe)")
    assert drop_redundant_rapids(text) == text
