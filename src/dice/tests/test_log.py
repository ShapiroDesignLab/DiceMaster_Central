from dice import log


def test_log_sends_to_logger(mock_runtime):
    log("hello world")
    assert ("info", "hello world") in mock_runtime._logger.messages
