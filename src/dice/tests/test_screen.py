from dice import screen


def test_set_text(mock_runtime):
    screen.set_text(1, "/assets/question.json")
    pub = mock_runtime.publishers_.get("/screen_1_cmd")
    assert pub is not None
    assert len(pub.messages) == 1
    msg = pub.messages[0]
    assert msg.screen_id == 1
    assert msg.media_type == 0
    assert msg.file_path == "/assets/question.json"


def test_set_image(mock_runtime):
    screen.set_image(2, "/assets/cat.jpg")
    pub = mock_runtime.publishers_.get("/screen_2_cmd")
    assert pub is not None
    msg = pub.messages[0]
    assert msg.screen_id == 2
    assert msg.media_type == 1
    assert msg.file_path == "/assets/cat.jpg"


def test_set_gif(mock_runtime):
    screen.set_gif(3, "/assets/anim.gif.d")
    pub = mock_runtime.publishers_.get("/screen_3_cmd")
    assert pub is not None
    msg = pub.messages[0]
    assert msg.screen_id == 3
    assert msg.media_type == 2
    assert msg.file_path == "/assets/anim.gif.d"


def test_publisher_reuse(mock_runtime):
    screen.set_text(1, "a.json")
    screen.set_image(1, "b.jpg")
    # Should reuse publisher, so only 1 publisher for screen 1
    screen_1_pubs = [k for k in mock_runtime.publishers_ if k == "/screen_1_cmd"]
    assert len(screen_1_pubs) == 1
    assert len(mock_runtime.publishers_["/screen_1_cmd"].messages) == 2
