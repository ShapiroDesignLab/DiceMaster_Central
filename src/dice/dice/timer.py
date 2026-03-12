_timers = {}
_next_id = 0
def _reset():
    global _next_id
    _timers.clear()
    _next_id = 0
