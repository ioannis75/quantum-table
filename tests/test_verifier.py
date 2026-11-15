import pytest
from qiskit import QuantumCircuit
from verifier.core import *
from verifier.sandbox import run_model_code, check_source, Rejected
from engines.aer import run_statevector

FAIR = '''from qiskit import QuantumCircuit
def build_circuit():
    qc = QuantumCircuit(1); qc.h(0); return qc
def expected():
    return {"0": 0.5, "1": 0.5}
'''
BIASED = FAIR.replace("qc.h(0)", "qc.ry(1.0, 0)")


def test_fair_passes():
    r = run_model_code(FAIR)
    out = run_statevector(r["circuit"], 4000)
    assert check_expectation(out["exact"], r["expected"])["ok"]
    assert check_counts(out["counts"], out["exact"])["ok"]


def test_biased_expectation_wrong():
    r = run_model_code(BIASED)
    out = run_statevector(r["circuit"], 1000)
    ex = check_expectation(out["exact"], r["expected"])
    assert not ex["ok"]
    assert badge(ex["ok"], None) == "EXPECTATION WRONG"


def test_corrupted_counts_fail():
    exact = {"0": 0.5, "1": 0.5}
    c = check_counts({"0": 700, "1": 300}, exact)
    assert not c["ok"] and badge(True, c["ok"]) == "CHECK FAILED"
    assert not check_counts({"0": 500, "1": 400, "11": 100}, exact)["ok"]


@pytest.mark.parametrize("src", ["import os", "from os import path", "import socket", "import subprocess",
                                 "x = eval('1')", "open('/etc/passwd')", "import qiskit.providers; q.__class__",
                                 "from qiskit import execute", "from qiskit import Aer", "from qiskit import IBMQ"])
def test_rejected(src):
    with pytest.raises(Rejected):
        check_source(src)


def test_sandbox_timeout_and_error():
    with pytest.raises(Rejected):
        run_model_code("def build_circuit():\n  while True: pass\ndef expected(): return {}", timeout=3)
    with pytest.raises(Rejected):
        run_model_code("def build_circuit():\n  raise ValueError('x')\ndef expected(): return {}")


def test_commit_hash_stable():
    a = commit_hash("code", {"0": 0.5, "1": 0.5})
    assert a == commit_hash("code", {"1": 0.5, "0": 0.5}) and a != commit_hash("code2", {"0": 0.5, "1": 0.5})
