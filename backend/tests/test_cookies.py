import os
import stat
from http.cookiejar import Cookie, MozillaCookieJar

from app.cookies import filter_youtube_cookies, write_cookie_file, ytdlp_auth_opts


def cookie(domain, name="c", value="v"):
    return Cookie(0, name, value, None, False, domain, True, domain.startswith("."), "/", True, True,
                  4102444800, False, None, None, {})


def jar_of(*domains):
    j = MozillaCookieJar()
    for i, d in enumerate(domains):
        j.set_cookie(cookie(d, name=f"c{i}"))
    return j


def test_filter_keeps_only_youtube_and_google_cookies():
    j = jar_of(".youtube.com", "www.youtube.com", ".google.com", "accounts.google.com", ".googlevideo.com",
               ".facebook.com", ".github.com", "mail.example.org", ".notyoutube.com")
    kept = {c.domain for c in filter_youtube_cookies(j)}
    assert kept == {".youtube.com", "www.youtube.com", ".google.com", "accounts.google.com", ".googlevideo.com"}


def test_write_cookie_file_is_private_and_roundtrips(tmp_path):
    out = tmp_path / "sub" / "yt.txt"
    n = write_cookie_file(jar_of(".youtube.com", ".google.com"), out)
    assert n == 2 and out.exists()
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600
    j = MozillaCookieJar(str(out))
    j.load(ignore_discard=True, ignore_expires=True)
    assert len(list(j)) == 2


def test_auth_opts_empty_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    assert ytdlp_auth_opts() == {}


def test_auth_opts_uses_default_exported_file_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    (tmp_path / "youtube_cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    assert open(ytdlp_auth_opts()["cookiefile"]).read() == (tmp_path / "youtube_cookies.txt").read_text()


def test_auth_opts_env_file_wins_and_missing_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    f = tmp_path / "mine.txt"
    f.write_text("x")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(f))
    assert open(ytdlp_auth_opts()["cookiefile"]).read() == "x"
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(tmp_path / "nope.txt"))
    assert ytdlp_auth_opts() == {}


def test_each_call_gets_a_private_copy_so_the_saved_file_stays_pristine(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    master = tmp_path / "youtube_cookies.txt"
    master.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t4102444800\tA\toriginal\n")
    a = ytdlp_auth_opts()["cookiefile"]
    b = ytdlp_auth_opts()["cookiefile"]
    assert a != b and a != str(master) and b != str(master)
    assert open(a).read() == master.read_text() == open(b).read()
    open(a, "w").write("# rotated by yt-dlp\n")  # what yt-dlp does when it exits
    assert "original" in master.read_text()  # the saved export is untouched
    assert stat.S_IMODE(os.stat(b).st_mode) == 0o600


def test_old_session_copies_are_pruned(tmp_path, monkeypatch):
    import time
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    (tmp_path / "youtube_cookies.txt").write_text("x")
    old = ytdlp_auth_opts()["cookiefile"]
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    ytdlp_auth_opts()
    assert not os.path.exists(old)
