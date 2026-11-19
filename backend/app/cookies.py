"""Optional YouTube login cookies for yt-dlp, for when YouTube answers "Sign in to confirm you're not a bot".

Only YouTube/Google cookies are ever stored, in a private file inside the data folder. Use a throwaway account:
automated use can get an account flagged. Export once with:  uv run python -m app.cookies chrome "Profile 5"
"""
import os
import shutil
import sys
import time
import uuid
from http.cookiejar import MozillaCookieJar
from pathlib import Path

from .config import get_settings

_DOMAINS = ("youtube.com", "google.com", "googlevideo.com")


def _is_youtube_domain(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return any(d == x or d.endswith("." + x) for x in _DOMAINS)


def filter_youtube_cookies(jar) -> list:
    return [c for c in jar if _is_youtube_domain(c.domain)]


def write_cookie_file(cookies, path: Path) -> int:
    """Write cookies as a Netscape cookie file readable only by the current user. Returns the count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = MozillaCookieJar()
    n = 0
    for c in cookies:
        out.set_cookie(c)
        n += 1
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.close(fd)
    out.save(str(path), ignore_discard=True, ignore_expires=True)
    os.chmod(path, 0o600)
    return n


def default_cookie_path() -> Path:
    return get_settings().data_dir / "youtube_cookies.txt"


def _session_copy(master: Path) -> str:
    """yt-dlp rewrites its cookie file on exit with whatever YouTube rotated, and those rotated cookies stop
    working. So every call works on a private throwaway copy and the exported master file stays pristine."""
    d = master.parent / ".cookie_sessions"
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in d.glob("*.txt"):
        if now - old.stat().st_mtime > 3600:
            old.unlink(missing_ok=True)
    dest = d / f"{uuid.uuid4().hex}.txt"
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.close(fd)
    shutil.copyfile(master, dest)
    os.chmod(dest, 0o600)
    return str(dest)


def ytdlp_auth_opts() -> dict:
    """yt-dlp options that add the exported cookies (as a private copy), if configured or exported."""
    env = os.environ.get("YTDLP_COOKIES_FILE")
    master = Path(env) if env else default_cookie_path()
    if not master.exists():
        return {}
    return {"cookiefile": _session_copy(master)}


def main(argv: list[str]) -> int:
    from yt_dlp.cookies import extract_cookies_from_browser

    if not argv:
        print('usage: python -m app.cookies <browser> [profile]   e.g. chrome "Profile 5"')
        return 2
    browser, profile = argv[0], (argv[1] if len(argv) > 1 else None)
    jar = extract_cookies_from_browser(browser, profile)
    kept = filter_youtube_cookies(jar)
    if not kept:
        print("No YouTube/Google cookies found in that profile (is the account signed in to YouTube there?).")
        return 1
    n = write_cookie_file(kept, default_cookie_path())
    print(f"Saved {n} YouTube/Google cookies to {default_cookie_path()} (private file). Nothing else was kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
