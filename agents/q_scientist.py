"""Q-Scientist: writes the Qiskit circuit code for the dice and states the exact expected distribution.
Model-written code runs only in the sandbox; one repair retry; then the scripted circuit. The verifier decides."""
import config
import db
from games.qraps import circuits
from games.qraps.modes import MODES
from verifier import core, sandbox
from . import llm, registry

SYSTEM = """You are Q-Scientist. Write Python (qiskit, numpy, math, itertools, fractions only) defining
build_circuit() -> QuantumCircuit (6 qubits, NO measurements: die A on qubits 0-2, die B on qubits 3-5, value = face-1 little-endian)
and expected() -> dict mapping 6-char bitstrings (Qiskit order, qubit 5 leftmost) to exact probabilities.
Prepare the state exactly with QuantumCircuit.prepare_state; faces 7 and 8 must never appear. Installed versions: {versions}.
Never use execute, Aer from qiskit, IBMQ or assemble. Reply with code only."""

_cache: dict = {}


def design(mode: str, allow_model: bool = True) -> dict:
    """Returns {mode, code, hash, expected, circuit, source, badge info}. Cached per mode."""
    if mode in _cache:
        return _cache[mode]
    registry.set_status("q_scientist", "working")
    code, source = None, "scripted circuits"
    if allow_model and config.has("ANTHROPIC_API_KEY"):
        pairs = MODES[mode]
        user = f"Mode {mode}: the pair (die A, die B) is uniform over exactly these {len(pairs)} pairs: {pairs}"
        for attempt in range(2):          # first try + one repair retry
            try:
                text, label = llm.anthropic_ask(SYSTEM.format(versions=config.versions()), user, "smart", 1200)
                src = text.strip().strip("`").removeprefix("python").strip()
                res = sandbox.run_model_code(src)
                chk = _check(res["circuit"], res["expected"], mode)
                if chk["ok"]:
                    code, source = src, label
                    break
                user += f"\nYour last attempt failed verification: {chk['why']}. Repair it."
            except Exception as e:
                user += f"\nYour last attempt failed: {str(e)[:150]}. Repair it."
    if code is None:
        code = circuits.design_code(mode)
        source = "scripted circuits" if not config.has("ANTHROPIC_API_KEY") else "scripted circuits (model attempt failed verification)"
    res = sandbox.run_model_code(code)
    chk = _check(res["circuit"], res["expected"], mode)
    out = {"mode": mode, "code": code, "hash": core.commit_hash(code, res["expected"]), "expected": res["expected"],
           "circuit": res["circuit"], "source": source, "expectation": chk["expectation"], "ok": chk["ok"]}
    _cache[mode] = out
    registry.set_status("q_scientist", "idle", source, f"design for {mode}")
    return out


def _check(circuit, expected, mode) -> dict:
    from engines.aer import run_statevector
    out = run_statevector(circuit, 64)
    ex = core.check_expectation(out["exact"], expected)
    table_ok = len([p for p in out["exact"].values() if p > 1e-12]) == len(MODES[mode]) and all(
        (int(k, 2) & 7) < 6 and ((int(k, 2) >> 3) & 7) < 6 for k, p in out["exact"].items() if p > 1e-12)
    why = "expectation differs from the circuit" if not ex["ok"] else ("circuit does not match the mode table" if not table_ok else "")
    return {"ok": ex["ok"] and table_ok, "expectation": ex, "why": why}
