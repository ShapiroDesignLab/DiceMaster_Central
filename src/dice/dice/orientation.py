_change_handlers = []
_top = 1
_bottom = 6
_subscribed = False
def _reset():
    global _top, _bottom, _subscribed
    _change_handlers.clear()
    _top = 1
    _bottom = 6
    _subscribed = False
