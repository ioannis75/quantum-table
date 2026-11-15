"""Table event stream: persisted, fanned out to SSE subscribers and the Host."""
import json
import threading
import time
import db

_subs: list = []
_lock = threading.Lock()
_listeners: list = []


def emit(type_: str, data: dict | None = None) -> dict:
    ev = {"ts": time.time(), "type": type_, "data": data or {}}
    db.q("INSERT INTO events(ts,type,data) VALUES(?,?,?)", (ev["ts"], type_, json.dumps(ev["data"])))
    with _lock:
        for s in list(_subs):
            try:
                s.append(ev)
            except Exception:
                pass
        ls = list(_listeners)
    for fn in ls:
        try:
            fn(ev)
        except Exception:
            pass
    return ev


def on(fn):
    _listeners.append(fn)


def subscribe() -> list:
    buf: list = []
    with _lock:
        _subs.append(buf)
    return buf


def unsubscribe(buf) -> None:
    with _lock:
        if buf in _subs:
            _subs.remove(buf)
