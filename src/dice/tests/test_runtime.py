from dice._runtime import get_node, teardown


def test_get_node_returns_mock(mock_runtime):
    node = get_node()
    assert node is mock_runtime


def test_teardown_clears_state(mock_runtime):
    from dice import motion
    called = []
    motion.on_shake(lambda i: called.append(i))
    teardown()
    assert len(motion._shake_handlers) == 0
