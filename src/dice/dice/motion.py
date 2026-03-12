_shake_handlers = []
_shaking = False
_intensity = 0.0
_subscribed = False

def on_shake(handler):
    _shake_handlers.append(handler)

def _reset():
    global _shaking, _intensity, _subscribed
    _shake_handlers.clear()
    _shaking = False
    _intensity = 0.0
    _subscribed = False
