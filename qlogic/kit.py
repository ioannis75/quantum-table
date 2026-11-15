"""Quantum-logic kit (Birkhoff-von Neumann). A proposition is a projector; the connectives act on SUBSPACES.
AND = intersection of subspaces, OR = span, NOT = orthogonal complement. Exact up to 1e-9.
Evaluated by ordinary code on an ordinary computer; no model does any algebra."""
import numpy as np
from scipy.linalg import null_space, orth

TOL = 1e-9
I2 = np.eye(2)
PAULI = {"X": np.array([[0, 1], [1, 0]], complex), "Y": np.array([[0, -1j], [1j, 0]], complex),
         "Z": np.array([[1, 0], [0, -1]], complex)}


def _proj_from_basis(B: np.ndarray, d: int) -> np.ndarray:
    if B.size == 0:
        return np.zeros((d, d), complex)
    return B @ B.conj().T


class QLogic:
    def __init__(self, n_qubits: int):
        self.n = n_qubits
        self.d = 2 ** n_qubits
        self.I = np.eye(self.d, dtype=complex)

    # ---- atoms -------------------------------------------------------------------------------
    def _die_vals(self, die: int) -> np.ndarray:
        idx = np.arange(self.d)
        return (idx >> (3 * die)) & 7

    def face(self, die: int, k: int) -> np.ndarray:
        return np.diag((self._die_vals(die) == k - 1).astype(complex))

    def total(self, n: int) -> np.ndarray:
        s = self._die_vals(0) + self._die_vals(1) + 2
        valid = (self._die_vals(0) < 6) & (self._die_vals(1) < 6)
        return np.diag(((s == n) & valid).astype(complex))

    def equal(self, a: int = 0, b: int = 1) -> np.ndarray:
        va, vb = self._die_vals(a), self._die_vals(b)
        return np.diag(((va == vb) & (va < 6)).astype(complex))

    def qubit(self, i: int, axis: str, sign: int) -> np.ndarray:
        ops = [I2] * self.n
        ops[i] = PAULI[axis.upper()]
        M = np.array([[1]], complex)
        for q in reversed(range(self.n)):      # qubit 0 = least significant
            M = np.kron(M, ops[q])
        return 0.5 * (self.I + sign * M)

    # ---- connectives (from subspaces, NOT from products/sums of matrices) ---------------------------
    def NOT(self, P):
        return self.I - P

    def AND(self, P, Q):
        N = null_space(np.vstack([self.I - P, self.I - Q]), rcond=1e-10)
        return _proj_from_basis(N, self.d)

    def OR(self, P, Q):
        B = orth(np.hstack([P, Q]), rcond=1e-10)
        return _proj_from_basis(B, self.d)

    # ---- queries -----------------------------------------------------------------------------
    def commutator_norm(self, P, Q) -> float:
        return float(np.linalg.norm(P @ Q - Q @ P))

    def compatible(self, P, Q) -> bool:
        return self.commutator_norm(P, Q) < TOL

    def prob(self, P, psi: np.ndarray) -> float:
        psi = psi / np.linalg.norm(psi)
        return float(np.real(psi.conj() @ P @ psi))

    def implies(self, P, Q) -> bool:
        return bool(np.linalg.norm(P - Q @ P) < TOL * 10)

    def dim(self, P) -> int:
        return int(round(np.real(np.trace(P))))

    # ---- JSON form (what the Logic designer writes) ---------------------------------------------
    def build(self, node):
        if "atom" in node:
            a = node["atom"]
            if a == "face":
                return self.face(int(node["die"]), int(node["k"]))
            if a == "sum":
                return self.total(int(node["n"]))
            if a == "equal":
                return self.equal(int(node.get("a", 0)), int(node.get("b", 1)))
            if a == "qubit":
                return self.qubit(int(node["i"]), node["axis"], int(node["sign"]))
            raise ValueError(f"unknown atom {a}")
        op = node["op"]
        args = [self.build(x) for x in node["args"]]
        if op == "not":
            return self.NOT(args[0])
        if op == "and":
            out = args[0]
            for a in args[1:]:
                out = self.AND(out, a)
            return out
        if op == "or":
            out = args[0]
            for a in args[1:]:
                out = self.OR(out, a)
            return out
        raise ValueError(f"unknown op {op}")


def pair_state(pairs: list) -> np.ndarray:
    """Prepared 2-dice state for a mode table (our reconstruction): uniform amplitudes on allowed pairs."""
    psi = np.zeros(64, complex)
    for a, b in pairs:
        psi[(a - 1) | ((b - 1) << 3)] = 1
    return psi / np.linalg.norm(psi)


def side_bet_check(ql: QLogic, p_json: dict, q_json: dict) -> dict:
    P, Q = ql.build(p_json), ql.build(q_json)
    c = ql.commutator_norm(P, Q)
    ok = c < TOL
    return {"allowed": ok, "commutator_norm": c,
            "message": "ok: can be checked in the same roll" if ok else "these two cannot be checked in the same roll"}


def distributivity_counterexample() -> dict:
    """A and (B or C) vs (A and B) or (A and C) on one qubit: A = up along X, B = up along Z, C = down along Z."""
    ql = QLogic(1)
    A, B, C = ql.qubit(0, "X", +1), ql.qubit(0, "Z", +1), ql.qubit(0, "Z", -1)
    psi = np.array([1, 1], complex) / np.sqrt(2)   # the X-up state
    lhs = ql.AND(A, ql.OR(B, C))
    rhs = ql.OR(ql.AND(A, B), ql.AND(A, C))
    return {"lhs_prob": ql.prob(lhs, psi), "rhs_prob": ql.prob(rhs, psi), "equal": abs(ql.prob(lhs, psi) - ql.prob(rhs, psi)) < TOL}


# ---- diagonal helpers for big registers (all dice atoms are diagonal projectors) -----------------------
def diag_face(n_qubits: int, die: int, k: int):
    idx = np.arange(2 ** n_qubits)
    return ((idx >> (3 * die)) & 7) == (k - 1)


def implies_on_state(P_diag, Q_diag, psi, tol: float = 1e-9) -> bool:
    """P implies Q on the state's support: every basis state with amplitude and P true also has Q true."""
    supp = np.abs(psi) ** 2 > tol
    return bool(np.all(Q_diag[supp & P_diag]))
