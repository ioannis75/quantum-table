"""SQLite storage (one file). Everything the show needs to replay or audit lives here."""
import json
import sqlite3
import threading
import time
from config import DB_PATH

_lock = threading.RLock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS players(id TEXT PRIMARY KEY, nick TEXT, qredits INTEGER, seat INTEGER, bot INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, type TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS rounds(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, data TEXT);
CREATE TABLE IF NOT EXISTS beacon(round INTEGER PRIMARY KEY, hash TEXT, record TEXT);
CREATE TABLE IF NOT EXISTS gate_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, agent TEXT, tool TEXT, purpose TEXT, est REAL, action TEXT, rule TEXT, engine TEXT, args TEXT);
CREATE TABLE IF NOT EXISTS qpu_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, job_hash TEXT, label TEXT, backend TEXT, job_id TEXT, qubits TEXT, est REAL, actual REAL, status TEXT, counts TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS qpu_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, job_hash TEXT, seconds REAL, source TEXT);
CREATE TABLE IF NOT EXISTS approvals(job_hash TEXT PRIMARY KEY, ts REAL);
CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, job_hash TEXT, kind TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS hype(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, card TEXT, origin TEXT, truth INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS probe(n INTEGER PRIMARY KEY, bytes REAL, seconds REAL, rss REAL, ok INTEGER, engine TEXT);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""
_conn = None


def conn():
    global _conn
    with _lock:
        if _conn is None:
            DB_PATH.parent.mkdir(exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def reset(path=None):
    """Used by tests: point at another file and drop the cached connection."""
    global _conn
    import config
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        if path:
            config.DB_PATH = type(config.DB_PATH)(path)
            globals()["DB_PATH"] = config.DB_PATH


def q(sql, args=()):
    with _lock:
        c = conn()
        cur = c.execute(sql, args)
        c.commit()
        return cur


def rows(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


def bump(name: str, n: int = 1) -> int:
    q("INSERT INTO counters(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=value+?", (name, n, n))
    return one("SELECT value FROM counters WHERE name=?", (name,))["value"]


def counter(name: str) -> int:
    r = one("SELECT value FROM counters WHERE name=?", (name,))
    return r["value"] if r else 0


def kv_get(k, default=None):
    r = one("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r["v"]) if r else default


def kv_set(k, v):
    q("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))
