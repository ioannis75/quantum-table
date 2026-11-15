"""Sandbox for model-written circuit code: AST allowlist + subprocess (timeout, memory cap, sockets disabled).
A policy-and-limits check, not a full OS sandbox."""
import ast
import base64
import io
import json
import subprocess
import sys

ALLOWED_IMPORTS = {"qiskit", "qiskit_aer", "numpy", "math", "itertools", "fractions"}
BANNED_NAMES = {"eval", "exec", "compile", "open", "__import__", "input", "globals", "locals",
                "getattr", "setattr", "delattr", "vars", "breakpoint", "exit", "quit"}
REMOVED_QISKIT = ["execute", "IBMQ", "assemble"]


class Rejected(Exception):
    pass


def check_source(src: str) -> None:
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise Rejected(f"syntax error: {e}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise Rejected(f"import not allowed: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORTS:
                raise Rejected(f"import not allowed: {node.module}")
            for a in node.names:
                if a.name in REMOVED_QISKIT or (root == "qiskit" and a.name == "Aer"):
                    raise Rejected(f"removed Qiskit API: {a.name}")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise Rejected(f"name not allowed: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in REMOVED_QISKIT:
                raise Rejected(f"attribute not allowed: {node.attr}")


RUNNER = r'''
import sys, json, base64, io, resource, socket
resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
def _blocked(*a, **k): raise RuntimeError("network disabled")
socket.socket = _blocked; socket.create_connection = _blocked
src = sys.stdin.read()
ns = {"__name__": "model_code"}
exec(compile(src, "model_code", "exec"), ns)
qc = ns["build_circuit"](); exp = ns["expected"]()
from qiskit import qpy
buf = io.BytesIO(); qpy.dump(qc, buf)
print(json.dumps({"qpy": base64.b64encode(buf.getvalue()).decode(), "expected": {k: float(v) for k, v in exp.items()}}))
'''


def run_model_code(src: str, timeout: int = 20) -> dict:
    """Returns {'circuit': QuantumCircuit, 'expected': dict}. Raises Rejected on any failure."""
    check_source(src)
    try:
        r = subprocess.run([sys.executable, "-I", "-c", RUNNER], input=src, capture_output=True,
                           text=True, timeout=timeout, env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "1"})
    except subprocess.TimeoutExpired:
        raise Rejected("timeout")
    if r.returncode != 0:
        raise Rejected("runtime error: " + r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else "runtime error")
    from qiskit import qpy
    out = json.loads(r.stdout.strip().splitlines()[-1])
    qc = qpy.load(io.BytesIO(base64.b64decode(out["qpy"])))[0]
    return {"circuit": qc, "expected": out["expected"]}
