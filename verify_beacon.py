#!/usr/bin/env python3
"""Don't trust us. Check it. Standard library only.
Usage:  python3 verify_beacon.py http://HOST:8080 [round]      (or a path to a saved round JSON file)
Recomputes commitments, the selection, the output and the hash-chain link; prints PASS or FAIL."""
import hashlib, json, sys, urllib.request

GENESIS = "0" * 64
sha = lambda b: hashlib.sha256(b).hexdigest()
canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"))


def fetch(src, rnd=None):
    if src.startswith("http"):
        url = src.rstrip("/") + ("/beacon/latest" if rnd is None else f"/beacon/{rnd}")
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    return json.load(open(src))


def check(rec, prev=None):
    problems = []
    for pid, secret in rec["reveals"].items():
        if sha(bytes.fromhex(secret)) != rec["commitments"].get(pid):
            problems.append(f"commitment mismatch for {pid}")
    acc = bytearray(32)
    for pid in sorted(rec["reveals"]):
        for i, b in enumerate(bytes.fromhex(rec["reveals"][pid])):
            acc[i] ^= b
    seed = sha(bytes(acc) + sha(canon(rec["counts"]).encode()).encode())
    pool = []
    for bs in sorted(rec["counts"]):
        pool += [bs] * rec["counts"][bs]
    chosen = []
    for i in range(min(8, len(pool))):
        j = int(sha((seed + str(i)).encode()), 16) % (len(pool) - i)
        pool[i], pool[i + j] = pool[i + j], pool[i]
        chosen.append(pool[i])
    out = sha((seed + ",".join(chosen)).encode())
    if out != rec["output"]:
        problems.append("output mismatch")
    if chosen[:1] != rec["selected"][:1]:
        problems.append("selected shot mismatch")
    body = {k: v for k, v in rec.items() if k != "hash"}
    if sha(canon(body).encode()) != rec["hash"]:
        problems.append("record hash mismatch")
    if prev is not None:
        if rec["prev_hash"] != prev["hash"]:
            problems.append("chain link mismatch")
    elif rec["round"] == 1 and rec["prev_hash"] != GENESIS:
        problems.append("first round must link to genesis")
    return problems


if __name__ == "__main__":
    src = sys.argv[1]
    rnd = int(sys.argv[2]) if len(sys.argv) > 2 else None
    rec = fetch(src, rnd)
    prev = None
    if src.startswith("http") and rec["round"] > 1:
        prev = fetch(src, rec["round"] - 1)
    probs = check(rec, prev)
    print(f"round {rec['round']} engine={rec['engine']}")
    print("PASS" if not probs else "FAIL: " + "; ".join(probs))
    sys.exit(0 if not probs else 1)
