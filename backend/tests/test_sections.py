import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app import sections
from app.sections import SectionUnavailable, download_section, parse_sidx_info, plan_segments

FLAGS = "frag_keyframe+empty_moov+default_base_moof+global_sidx"


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


def dur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,start_time", "-of", "json",
                          str(p)], capture_output=True, text=True, check=True).stdout
    f = json.loads(out)["format"]
    return float(f["duration"]), float(f.get("start_time", 0))


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("dash")
    ff("-f", "lavfi", "-i", "testsrc=d=60:s=320x180:r=25", "-c:v", "libx264", "-g", "50", "-keyint_min", "50",
       "-sc_threshold", "0", "-pix_fmt", "yuv420p", "-movflags", FLAGS, "-f", "mp4", str(d / "v.mp4"))
    ff("-f", "lavfi", "-i", "sine=d=60", "-c:a", "aac", "-frag_duration", "3000000", "-movflags", FLAGS,
       "-f", "mp4", str(d / "a.mp4"))
    ff("-f", "lavfi", "-i", "testsrc=d=10:s=64x64:r=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "plain.mp4"))
    return d


class Handler(BaseHTTPRequestHandler):
    root = None
    served = {}
    fail_once = set()

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        f = self.root / u.path.lstrip("/")
        data = f.read_bytes()
        rng = None
        if "range" in parse_qs(u.query):
            rng = parse_qs(u.query)["range"][0]
        elif self.headers.get("Range"):
            rng = self.headers["Range"].split("=")[1]
        if rng and (u.path not in Handler.fail_once):
            pass
        if u.path in Handler.fail_once:
            Handler.fail_once.discard(u.path)
            self.send_response(500)
            self.end_headers()
            return
        a, b = (int(x) if x else None for x in rng.split("-")) if rng else (0, len(data) - 1)
        b = len(data) - 1 if b is None else min(b, len(data) - 1)
        chunk = data[a:b + 1]
        Handler.served[u.path] = Handler.served.get(u.path, 0) + len(chunk)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Length", str(len(chunk)))
        self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
        self.end_headers()
        self.wfile.write(chunk)


@pytest.fixture
def server(media):
    Handler.root, Handler.served, Handler.fail_once = media, {}, set()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_parse_sidx_matches_the_file(media):
    data = (media / "v.mp4").read_bytes()
    info = parse_sidx_info(data)
    assert len(info.refs) >= 25 and info.timescale > 0
    assert info.sidx_start < info.sidx_end <= len(data)
    covered = info.sidx_end + info.first_offset + sum(r.size for r in info.refs)
    assert 0 <= len(data) - covered < 2048  # ffmpeg may append a small index box (mfra) after the segments


def test_parse_sidx_returns_none_when_not_present_or_too_short(media):
    assert parse_sidx_info((media / "plain.mp4").read_bytes()) is None
    assert parse_sidx_info(b"\x00\x00") is None


def test_plan_segments_covers_the_requested_window(media):
    info = parse_sidx_info((media / "v.mp4").read_bytes())
    p = plan_segments(info, 10, 20)
    assert p.start_time <= 10 and p.end_time >= 20
    assert p.start_time > 10 - 2 * 2.5 and p.end_time < 20 + 2 * 2.5  # within about one segment each side
    assert p.byte_start >= info.sidx_end and p.byte_end <= info.sidx_end + info.first_offset + sum(r.size for r in info.refs)


def test_download_section_fetches_only_the_needed_bytes(media, server, tmp_path, monkeypatch):
    monkeypatch.setattr(sections, "HEAD_BYTES", 16 * 1024)  # real files are huge; the test files are tiny
    out = tmp_path / "o.mp4"
    res = download_section(f"{server}/v.mp4", f"{server}/a.mp4", 20, 30, out, chunk=64 * 1024)
    d, _ = dur(out)
    assert 9 <= d <= 16, d
    assert res.actual_start <= 20 and 20 - res.actual_start <= 6
    total = (media / "v.mp4").stat().st_size + (media / "a.mp4").stat().st_size
    assert sum(Handler.served.values()) < 0.6 * total  # a 10 s window of a 60 s file must not download it all


def test_download_section_without_audio_url(media, server, tmp_path):
    out = tmp_path / "o.mp4"
    download_section(f"{server}/v.mp4", None, 5, 15, out, chunk=64 * 1024)
    assert dur(out)[0] >= 9


def test_plain_mp4_raises_section_unavailable(media, server, tmp_path):
    with pytest.raises(SectionUnavailable):
        download_section(f"{server}/plain.mp4", None, 1, 5, tmp_path / "o.mp4")


def test_chunk_failure_is_retried(media, server, tmp_path):
    Handler.fail_once.add("/v.mp4")
    out = tmp_path / "o.mp4"
    download_section(f"{server}/v.mp4", None, 5, 15, out, chunk=64 * 1024)
    assert dur(out)[0] >= 9


def test_window_past_the_end_is_clamped_or_rejected(media, server, tmp_path):
    out = tmp_path / "o.mp4"
    download_section(f"{server}/v.mp4", None, 50, 90, out, chunk=64 * 1024)  # video is only 60 s
    assert 5 <= dur(out)[0] <= 12
    with pytest.raises(SectionUnavailable):
        download_section(f"{server}/v.mp4", None, 100, 130, tmp_path / "x.mp4")


def test_header_larger_than_first_fetch_is_read_in_full(media, server, tmp_path, monkeypatch):
    monkeypatch.setattr(sections, "HEAD_BYTES", 300)  # smaller than moov: must fetch more before finding sidx
    out = tmp_path / "o.mp4"
    download_section(f"{server}/v.mp4", None, 5, 15, out, chunk=64 * 1024)
    assert dur(out)[0] >= 9
