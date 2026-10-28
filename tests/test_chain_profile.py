# SPDX-License-Identifier: LGPL-2.1-or-later
"""PathTurnBase.chain_profile: FreeCAD's section edges in any order, chained front to back."""

import math

from PathTurnScripts.PathTurnBase import chain_profile


def edge(p0, p1, mid=None, angle=0):
    return {"p0": p0, "p1": p1, "mid": mid, "angle": angle}


def test_chains_reversed_edges_from_the_front_on_the_axis():
    items = [edge((-5, 0), (-5, 10)), edge((-5, 0), (0, 0)), edge((-5, 10), (0, 10))]
    chain, left = chain_profile(items)
    assert left == 0
    assert [(s, e) for s, e, _ in chain] == [((0, 10), (-5, 10)), ((-5, 10), (-5, 0)), ((-5, 0), (0, 0))]


def test_counts_edges_not_connected_to_the_profile():
    items = [edge((0, 10), (-5, 10)), edge((-5, 10), (-5, 0)), edge((-20, 50), (-21, 50))]
    chain, left = chain_profile(items)
    assert len(chain) == 2 and left == 1


def test_snaps_near_axis_x_to_zero():
    chain, _ = chain_profile([edge((1e-5, 10), (-5, 10))])
    assert chain[0][0] == (0.0, 10)


def test_arc_sign_follows_the_side_of_the_bulge():
    s, e = (0, 10), (-5, 5)
    r = 5 / math.sqrt(2)
    out, _ = chain_profile([edge(s, e, mid=(-r, 5 + r), angle=math.pi / 2)])     # centre (0, 5)
    inward, _ = chain_profile([edge(s, e, mid=(-5 + r, 10 - r), angle=math.pi / 2)])  # centre (-5, 10)
    assert out[0][2] == -math.pi / 2
    assert inward[0][2] == math.pi / 2
