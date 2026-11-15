import numpy as np
import pytest
from qlogic.kit import QLogic, pair_state, distributivity_counterexample, side_bet_check
from games.qraps.modes import MODES, total_dist


def test_projectors():
    ql = QLogic(1)
    for ax in "XYZ":
        P = ql.qubit(0, ax, 1)
        assert np.allclose(P @ P, P) and np.allclose(P, P.conj().T) and ql.dim(P) == 1
        assert np.allclose(P + ql.qubit(0, ax, -1), np.eye(2))


def test_and_or_from_subspaces_not_products():
    ql = QLogic(1)
    A, B = ql.qubit(0, "X", 1), ql.qubit(0, "Z", 1)
    assert ql.dim(ql.AND(A, B)) == 0          # distinct rays meet only at 0
    assert ql.dim(ql.OR(A, B)) == 2           # and span everything
    assert not np.allclose(ql.AND(A, B), A @ B)   # the product is not even a projector here


def test_distributive_law_fails():
    r = distributivity_counterexample()
    assert abs(r["lhs_prob"] - 1) < 1e-9 and abs(r["rhs_prob"]) < 1e-9 and not r["equal"]


def test_compatibility():
    ql = QLogic(6)
    assert ql.compatible(ql.face(0, 3), ql.total(7))
    assert not ql.compatible(ql.face(0, 3), ql.qubit(0, "X", 1))
    assert not side_bet_check(ql, {"atom": "face", "die": 0, "k": 3}, {"atom": "qubit", "i": 0, "axis": "X", "sign": 1})["allowed"]


@pytest.mark.parametrize("mode", list(MODES))
def test_born_rule_matches_enumeration(mode):
    ql = QLogic(6)
    psi = pair_state(MODES[mode])
    td = total_dist(mode)
    win = ql.build({"op": "or", "args": [{"atom": "sum", "n": 7}, {"atom": "sum", "n": 11}]})
    assert abs(ql.prob(win, psi) - float(td.get(7, 0) + td.get(11, 0))) < 1e-9
    eq = ql.build({"atom": "equal"})
    assert abs(ql.prob(eq, psi) - sum(1 for a, b in MODES[mode] if a == b) / len(MODES[mode])) < 1e-9


def test_implies():
    ql = QLogic(6)
    assert ql.implies(ql.total(7), ql.NOT(ql.total(11)))
    assert ql.implies(ql.AND(ql.face(0, 3), ql.face(1, 4)), ql.total(7))
    assert not ql.implies(ql.total(7), ql.face(0, 3))
