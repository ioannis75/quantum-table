import math
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def tmpdb(tmp_path):
    import db
    db.reset(str(tmp_path / "t.db"))
    from games import chipgame
    chipgame.reset()
    yield
    db.reset(str(ROOT / "data" / "quantum_table.db"))


def test_exact_distributions_and_entropy():
    from games import chipgame as g
    import numpy as np
    from qiskit.quantum_info import Statevector
    from verifier.core import check_expectation
    for ent in (True, False):
        qc = g.table_circuit(ent)
        exact = {format(i, "012b"): float(x) for i, x in enumerate(np.abs(Statevector(qc).data) ** 2) if x > 1e-15}
        assert check_expectation(exact, g.expected_table(ent))["ok"]
        for b in exact:                       # no invalid faces in the exact circuit
            d = g.decode(b)
            assert None not in d["house"] + d["player"]
        if ent:
            assert all(g.decode(b)["house"] == g.decode(b)["player"] for b in exact)
    assert abs(g.entanglement_entropy(True) - math.log2(6)) < 1e-9
    assert g.entanglement_entropy(False) < 1e-9


def test_layout_distinct_and_on_chip():
    from games import chipgame as g
    from engines import ibm
    n = ibm.fake_backend().num_qubits
    seen = set()
    for seat in range(1, 8):
        L = g.assign_layout(seat)
        qs = [q for d in L["house"] + L["player"] for q in d]
        assert len(qs) == 12 and all(0 <= q < n for q in qs) and not (set(qs) & seen)
        seen |= set(qs)
        assert len(L["links"]) == 6 and all(a in sum(L["house"], []) and b in sum(L["player"], []) for a, b in L["links"])


def test_roll_flow_and_aggregate():
    from games import chipgame as g
    p = g.join("Ana")
    r = g.roll(p["id"], level=1.0, shots=1)
    assert r["entangled"] and r["expectation"]["ok"] and 0 < r["fidelity"]["fidelity"] <= 1
    assert r["badge"].startswith("VERIFIED") and "aggregate 1 rolls" in r["badge"]
    r = g.roll(p["id"], level=1.0, shots=100)
    assert r["aggregate"]["shots"] == 101 and r["aggregate"]["ideal_check"]["ok"]
    assert r["faces"]["house"][0] is None or 1 <= r["faces"]["house"][0] <= 6
    r0 = g.roll(p["id"], level=0.0, shots=1)
    assert not r0["entangled"] and r0["aggregate"]["settings"] == "independent"
    with pytest.raises(ValueError):
        g.roll("nobody")
