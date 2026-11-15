import numpy as np
from fractions import Fraction
import pytest
from games.qraps.modes import *
from games.qraps.circuits import *
from verifier.sandbox import run_model_code
from verifier.core import check_expectation, check_counts, correlation_check
from engines.aer import run_statevector
from qiskit import QuantumCircuit


def test_original_tables():
    assert [len(MODES[m]) for m in MODES] == [36, 21, 15, 6, 3]
    assert (2, 2) in BOSONIC and (2, 1) not in BOSONIC
    assert all(a < b for a, b in FERMIONIC)
    assert FERMIONIC_ENT == [(1, 6), (2, 5), (3, 4)]


def test_classical_odds_known():
    assert craps_win_probability("Classical") == Fraction(244, 495)


@pytest.mark.parametrize("m", list(MODES))
def test_odds_match_series(m):
    assert abs(float(craps_win_probability(m)) - craps_win_probability_series(m)) < 1e-9


@pytest.mark.parametrize("m", list(MODES))
def test_design_matches_table_exactly(m):
    r = run_model_code(design_code(m))
    out = run_statevector(r["circuit"], 256)
    assert check_expectation(out["exact"], r["expected"])["ok"]
    assert len([p for p in out["exact"].values() if p > 1e-12]) == len(MODES[m])


@pytest.mark.parametrize("m", list(MODES))
@pytest.mark.parametrize("n", [1, 2])
def test_table_circuit_and_correlation(m, n):
    r = run_model_code(design_code(m))
    rule = CROSS_RULE[m]
    tc = table_circuit(r["circuit"], n, rule)
    out = run_statevector(tc, 2000, seed=7)
    assert check_expectation(out["exact"], expected_table(MODES[m], n, rule))["ok"]
    assert check_counts(out["counts"], out["exact"])["ok"]
    samples = []
    for bs, c in out["counts"].items():
        f = decode(bs, n)
        assert (f[0], f[1]) in MODES[m]          # no invalid faces
        for p in range(1, n + 1):
            samples.append(((f[0], f[1]), (f[2 * p], f[2 * p + 1])))
    assert correlation_check(samples, rule)["ok"]


def test_bloch_basis_and_bell():
    z = QuantumCircuit(1)
    v = bloch_vectors(z)[0]
    assert abs(v[2] - 1) < 1e-12 and np.linalg.norm(v) > 1 - 1e-12
    bell = QuantumCircuit(2); bell.h(0); bell.cx(0, 1)
    for v in bloch_vectors(bell):
        assert np.linalg.norm(v) < 1e-12


def test_entangled_dice_arrows_shrink():
    """Entangling with the house shrinks each single-qubit arrow (it is mixed); some reach the centre.
    The top bit of a 0..5 die value is 1 only for faces 5,6, so that arrow keeps length |2/3-1/3| = 1/3."""
    r = run_model_code(design_code("BosonicEntangled"))
    prep = bloch_vectors(r["circuit"])
    ent = bloch_vectors(table_circuit(r["circuit"], 1, "equal"))[:6]
    L = lambda v: float(np.linalg.norm(v))
    assert all(L(e) < 1 - 1e-6 for e in ent)
    assert all(L(e) <= L(p) + 1e-9 for e, p in zip(ent, prep))
    assert min(L(e) for e in ent) < 1e-9
