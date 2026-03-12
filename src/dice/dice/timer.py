"""Timers — periodic and one-shot callbacks."""
from __future__ import annotations
import threading

_timers: dict[int, threading.Timer | threading.Event] = {}
_next_id: int = 0
_lock = threading.Lock()


def set(interval: float, callback) -> int:
    global _next_id
    with _lock:
        tid = _next_id
        _next_id += 1
    stop_event = threading.Event()
    _timers[tid] = stop_event
    def loop():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if not stop_event.is_set():
                callback()
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return tid


def once(delay: float, callback) -> int:
    global _next_id
    with _lock:
        tid = _next_id
        _next_id += 1
    t = threading.Timer(delay, callback)
    t.daemon = True
    _timers[tid] = t
    t.start()
    return tid


def cancel(timer_id: int) -> None:
    obj = _timers.pop(timer_id, None)
    if obj is None:
        return
    if isinstance(obj, threading.Event):
        obj.set()
    elif isinstance(obj, threading.Timer):
        obj.cancel()


def _reset() -> None:
    global _next_id
    for tid in list(_timers.keys()):
        cancel(tid)
    _timers.clear()
    _next_id = 0
