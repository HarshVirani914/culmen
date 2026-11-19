from app.live.storage import enforce_cap


def make(root, name, size):
    d = root / name
    d.mkdir()
    (d / "video.mp4").write_bytes(b"x" * size)


def test_deletes_oldest_first_until_under_cap(tmp_path):
    for n in ("a", "b", "c", "d"):
        make(tmp_path, n, 100)
    gone = enforce_cap(tmp_path, ["a", "b", "c", "d"], cap_bytes=250, keep=set())
    assert gone == ["a", "b"]
    assert not (tmp_path / "a").exists() and (tmp_path / "d").exists()


def test_never_deletes_kept_ids(tmp_path):
    for n in ("a", "b", "c"):
        make(tmp_path, n, 100)
    gone = enforce_cap(tmp_path, ["a", "b", "c"], cap_bytes=100, keep={"a"})
    assert "a" not in gone and (tmp_path / "a").exists() and gone == ["b", "c"]


def test_under_cap_deletes_nothing_and_ignores_missing_ids(tmp_path):
    make(tmp_path, "a", 10)
    assert enforce_cap(tmp_path, ["a", "ghost"], cap_bytes=1000, keep=set()) == []
