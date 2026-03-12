from dice import assets


def test_get_existing(mock_runtime, tmp_path, monkeypatch):
    (tmp_path / "cat.jpg").touch()
    monkeypatch.setattr(assets, "_assets_root", str(tmp_path))
    assert assets.get("cat.jpg") == str(tmp_path / "cat.jpg")


def test_get_nested(mock_runtime, tmp_path, monkeypatch):
    (tmp_path / "cats").mkdir()
    (tmp_path / "cats" / "cat1.jpg").touch()
    monkeypatch.setattr(assets, "_assets_root", str(tmp_path))
    assert assets.get("cats/cat1.jpg") == str(tmp_path / "cats" / "cat1.jpg")


def test_list_all(mock_runtime, tmp_path, monkeypatch):
    (tmp_path / "a.jpg").touch()
    (tmp_path / "b.json").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.jpg").touch()
    monkeypatch.setattr(assets, "_assets_root", str(tmp_path))
    result = assets.list_all()
    assert "a.jpg" in result
    assert "b.json" in result
    assert "sub/c.jpg" in result
