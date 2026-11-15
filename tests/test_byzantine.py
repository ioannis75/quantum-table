import numpy as np
from games import byzantine as bz
from qiskit.quantum_info import Statevector
from verifier.core import check_expectation


def test_singlet_exact_and_rule():
    amp = bz.singlet_amplitudes()
    assert abs(np.linalg.norm(amp) - 1) < 1e-12
    exact = {format(i, "06b"): float(x) for i, x in enumerate(np.abs(Statevector(bz.circuit()).data) ** 2) if x > 1e-15}
    assert check_expectation(exact, bz.expected())["ok"] and len(exact) == 6
    assert all(len(set(bz.decode(b))) == 3 for b in exact)       # three different outcomes, always


def test_invariance_under_common_basis_and_run():
    r = bz.run(shots=1500, seed=5)
    assert r["expectation"]["ok"] and r["counts_check"]["ok"]
    assert r["all_different_z"] and r["all_different_rotated"] and r["rotated_check"]["ok"]
    assert r["liar_demo"]["inconsistent"] and r["badge"] == "VERIFIED"
