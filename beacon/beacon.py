"""The beacon: collectively generated, publicly checkable randomness (a small playful cousin of NIST/CU Boulder's CURBy;
weaker guarantees). Commit-reveal of every participant's 32-byte secret + the round's quantum counts."""
import hashlib
import json
import os
import time
import db

GENESIS = "0" * 64
SELECTION_RULE = ("seed = SHA256(XOR(all revealed secrets) || SHA256(canonical counts)); shots are listed in sorted-bitstring "
                  "order (each repeated by its count); partial Fisher-Yates driven by SHA256(seed || i) picks the order; "
                  "output = SHA256(seed || selected bitstrings joined by ','); the round outcome is the first selected shot.")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def new_secret() -> str:
    return os.urandom(32).hex()


def commitment(secret_hex: str) -> str:
    return sha(bytes.fromhex(secret_hex))


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def xor_secrets(secrets: list) -> bytes:
    acc = bytearray(32)
    for s in secrets:
        for i, b in enumerate(bytes.fromhex(s)):
            acc[i] ^= b
    return bytes(acc)


def select(counts: dict, reveals: dict, k: int = 8):
    """Returns (seed_hex, selected_bitstrings, output_hex). Pure function: verify_beacon.py re-implements it with stdlib."""
    x = xor_secrets([reveals[p] for p in sorted(reveals)])
    seed = sha(x + sha(canon(counts).encode()).encode())
    shots = []
    for bs in sorted(counts):
        shots += [bs] * counts[bs]
    chosen = []
    pool = list(shots)
    for i in range(min(k, len(pool))):
        j = int(sha((seed + str(i)).encode()), 16) % (len(pool) - i)
        pool[i], pool[i + j] = pool[i + j], pool[i]
        chosen.append(pool[i])
    out = sha((seed + ",".join(chosen)).encode())
    return seed, chosen, out


def latest():
    r = db.one("SELECT * FROM beacon ORDER BY round DESC LIMIT 1")
    return json.loads(r["record"]) if r else None


def get(round_id: int):
    r = db.one("SELECT record FROM beacon WHERE round=?", (round_id,))
    return json.loads(r["record"]) if r else None


def publish(record: dict) -> dict:
    prev = latest()
    record = dict(record)
    record["prev_hash"] = prev["hash"] if prev else GENESIS
    record["selection_rule"] = SELECTION_RULE
    body = dict(record)
    record["hash"] = sha(canon(body).encode())
    db.q("INSERT OR REPLACE INTO beacon(round,hash,record) VALUES(?,?,?)", (record["round"], record["hash"], json.dumps(record)))
    return record
