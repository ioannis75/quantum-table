import json
import subprocess
import sys
import time
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def tmpdb(tmp_path):
    import db
    db.reset(str(tmp_path / "t.db"))
    yield
    db.reset(str(ROOT / "data" / "quantum_table.db"))


def test_beacon_roundtrip_and_chain():
    from beacon import beacon
    s = {p: beacon.new_secret() for p in ("house", "p1", "agent:host")}
    counts = {"000111": 3, "111000": 5}
    seed, chosen, out = beacon.select(counts, s)
    assert len(chosen) == 8 and set(chosen) <= set(counts)
    seed2, chosen2, out2 = beacon.select(counts, s)
    assert (seed, chosen, out) == (seed2, chosen2, out2)
    s2 = dict(s); s2["p1"] = beacon.new_secret()          # one changed secret changes everything
    assert beacon.select(counts, s2)[2] != out
    rec1 = beacon.publish({"round": 1, "engine": "Aer emulator", "commitments": {p: beacon.commitment(x) for p, x in s.items()},
                           "reveals": s, "counts": counts, "selected": chosen, "output": out, "dropped": []})
    assert rec1["prev_hash"] == beacon.GENESIS
    rec2 = beacon.publish({"round": 2, "engine": "Aer emulator", "commitments": {p: beacon.commitment(x) for p, x in s.items()},
                           "reveals": s, "counts": counts, "selected": chosen, "output": out, "dropped": []})
    assert rec2["prev_hash"] == rec1["hash"]
    for rec, prev in ((rec1, None), (rec2, rec1)):
        f = ROOT / "data" / f"_t_{rec['round']}.json"; f.write_text(json.dumps(rec))
        r = subprocess.run([sys.executable, "-I", str(ROOT / "verify_beacon.py"), str(f)], capture_output=True, text=True)
        f.unlink()
        assert "PASS" in r.stdout, r.stdout + r.stderr
    bad = dict(rec2); bad["output"] = "00" * 32
    f = ROOT / "data" / "_t_bad.json"; f.write_text(json.dumps(bad))
    r = subprocess.run([sys.executable, "-I", str(ROOT / "verify_beacon.py"), str(f)], capture_output=True, text=True)
    f.unlink()
    assert "FAIL" in r.stdout


def test_seed_deck_all_computable_and_expected_verdicts():
    from games import hype
    want = {"fermionic-doubles": True, "no-signalling": False, "marginal-uniform": True, "measure-twice": False,
            "cheat-sheet": False, "all-36": False, "distributive": False, "sum7": True, "classical-less-half": True}
    for c in hype.SEED_DECK:
        r = hype.run_card(c)
        assert r["truth"] == want[c["id"]], (c["id"], r)
    assert not hype.validate({"id": "x", "sentence": "x", "origin": "t", "check": {"type": "nonsense"}})


def test_host_checker():
    from agents import host
    ev = {"type": "player_joined", "data": {"nick": "Ana", "qredits": 100, "qubits": 12}}
    assert host.check_line("Ana joins with 100 Qredits, 12 qubits now!", ev["data"])[0]
    assert not host.check_line("Ana joins with 100 Qredits, 13 qubits now!", ev["data"])[0]
    assert not host.check_line("Truly random dice, Ana!", ev["data"])[0]
    assert not host.check_line("Keep playing, Ana!", ev["data"])[0]
    sample = {"nick": "Ana", "qredits": 100, "qubits": 12, "round": 3, "faces": "6-1", "engine": "Aer emulator", "badge": "VERIFIED",
              "truth": True, "headline": "", "winner": "Classical", "action": "BLOCK", "rule": "r", "job_hash": "h", "label": "L",
              "est": 2.27, "bytes": 17179869184, "dropped": 1, "rule_text": "", "url": "u"}
    for t, fn in host.T.items():
        line = fn(sample)
        ok, why = host.check_line(line, sample)
        assert ok and len(line.split()) <= 25, (t, line, why)
    rec = host.react(ev, use_model=False)
    assert rec["source"] == "template" and host.check_line(rec["line"], ev["data"])[0]


def test_vote_deterministic():
    from agents.vote import vote
    conf = {"a": {"x": 0.9, "y": 0.1}, "b": {"x": 0.8, "y": 0.3}}
    r1 = vote(conf, ["x", "y"]); r2 = vote(conf, ["x", "y"])
    assert r1["ballots"] == r2["ballots"] and r1["winner"] == "x"


def test_gated_chip_flow_and_finance():
    import engines.ibm as ibm
    from agents import financial
    m = ibm.chip_map()
    assert len(m["pairs"]) == 144 and all(5 <= p["price"] <= 20 for p in m["pairs"])
    pairs = [{"player": "a", "nick": "a", "u": m["pairs"][0]["u"], "v": m["pairs"][0]["v"]}]
    r = ibm.submit_qpu_job({"pairs": pairs, "shots": 200})
    assert r["status"] == "done" and r["label"] == ibm.FAKE_LABEL and r["decision"] == "ALLOW"
    assert set(r["per_pair"][0]) <= {"00", "01", "10", "11"} and sum(r["per_pair"][0].values()) == 200
    assert ibm.submit_qpu_job({"pairs": pairs, "shots": 6000, "circuits": 200})["decision"] == "BLOCK"
    w = ibm.submit_qpu_job({"pairs": pairs, "shots": 100000})
    assert w["status"] == "waiting for approval"
    assert financial.try_charge_player()["action"] == "BLOCK"
    q = financial.quote("abc", 2.5)
    assert q["gate"] == "ALLOW"
    assert financial.ledger_summary()["invoices"] >= 0
