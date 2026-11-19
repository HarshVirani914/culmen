"""Fast section download for DASH mp4 files (what YouTube serves for processed videos).

yt-dlp cuts sections by handing the URL to ffmpeg, which reads it over one throttled connection (about 0.6x
realtime). These files carry a `sidx` index of every few-second segment, so we can compute the byte range of a
time window, fetch only that with many parallel chunked requests, and join it locally.
"""
import os
import struct
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import ffmpeg_bin

HEAD_BYTES = 2 * 1024 * 1024
MAX_HEAD_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024


class SectionUnavailable(Exception):
    """This file/format can't be cut this way (no sidx index, time window outside the video, ...)."""


@dataclass
class Ref:
    size: int
    duration: int


@dataclass
class SidxInfo:
    timescale: int
    earliest_pts: int
    first_offset: int
    refs: list[Ref]
    sidx_start: int
    sidx_end: int


@dataclass
class Plan:
    start_time: float
    end_time: float
    byte_start: int
    byte_end: int  # inclusive


@dataclass
class SectionResult:
    actual_start: float
    duration: float
    bytes_downloaded: int


def _scan(data: bytes) -> tuple[SidxInfo | None, int | None]:
    """Walk top-level boxes. Returns (info, None) when found, (None, n) if n bytes are needed to continue,
    (None, None) when there is no sidx."""
    pos = 0
    while pos + 8 <= len(data):
        size, typ = struct.unpack(">I4s", data[pos:pos + 8])
        hdr = 8
        if size == 1:
            if pos + 16 > len(data):
                return None, pos + 16
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            hdr = 16
        if size < hdr:
            return None, None
        if typ == b"sidx":
            if pos + size > len(data):
                return None, pos + size
            return _parse_sidx(data[pos + hdr:pos + size], pos, pos + size), None
        if typ in (b"moof", b"mdat"):
            return None, None  # media started without an index
        if pos + size > len(data):
            return None, pos + size + 8  # skip a big box (moov) then look at the next header
        pos += size
    return None, (pos + 8 if pos + 8 > len(data) else None)


def _parse_sidx(p: bytes, start: int, end: int) -> SidxInfo | None:
    version = p[0]
    timescale = struct.unpack(">I", p[8:12])[0]
    if version == 0:
        ept, first_offset = struct.unpack(">II", p[12:20])
        pos = 20
    else:
        ept, first_offset = struct.unpack(">QQ", p[12:28])
        pos = 28
    count = struct.unpack(">H", p[pos + 2:pos + 4])[0]
    pos += 4
    refs = []
    for _ in range(count):
        word, duration, _sap = struct.unpack(">III", p[pos:pos + 12])
        if word >> 31:  # hierarchical sidx: not supported
            return None
        refs.append(Ref(word & 0x7FFFFFFF, duration))
        pos += 12
    if not refs or timescale == 0:
        return None
    return SidxInfo(timescale, ept, first_offset, refs, start, end)


def parse_sidx_info(data: bytes) -> SidxInfo | None:
    return _scan(data)[0]


def plan_segments(info: SidxInfo, start: float, end: float) -> Plan:
    t = info.earliest_pts
    starts, ends = [], []
    for r in info.refs:
        starts.append(t / info.timescale)
        t += r.duration
        ends.append(t / info.timescale)
    if start >= ends[-1]:
        raise SectionUnavailable("the time window is past the end of this video")
    i0 = max((i for i, s in enumerate(starts) if s <= start), default=0)
    i1 = max((i for i, s in enumerate(starts) if s < end), default=i0)
    i1 = max(i1, i0)
    base = info.sidx_end + info.first_offset
    byte_start = base + sum(r.size for r in info.refs[:i0])
    byte_end = base + sum(r.size for r in info.refs[:i1 + 1]) - 1
    return Plan(starts[i0], ends[i1], byte_start, byte_end)


def _fetch(client: httpx.Client, url: str, a: int, b: int, headers: dict | None, tries: int = 5) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            if "googlevideo.com" in url:  # YouTube wants the range as a query parameter
                sep = "&" if "?" in url else "?"
                r = client.get(f"{url}{sep}range={a}-{b}", headers=headers)
            else:
                r = client.get(url, headers={**(headers or {}), "Range": f"bytes={a}-{b}"})
            if r.status_code in (200, 206):
                return r.content[: b - a + 1] if r.status_code == 200 and a == 0 else r.content
            last = RuntimeError(f"HTTP {r.status_code}")
        except httpx.HTTPError as e:
            last = e
        time.sleep(min(0.2 * 2 ** attempt, 3))
    raise RuntimeError(f"download failed: {last}")


def _fetch_part(client: httpx.Client, url: str, start: float, end: float, dest: Path, headers: dict | None,
                chunk: int, workers: int) -> tuple[Plan, int]:
    head = _fetch(client, url, 0, HEAD_BYTES - 1, headers)
    info = None
    while True:
        info, need = _scan(head)
        if info or not need or need > MAX_HEAD_BYTES:
            break
        head = _fetch(client, url, 0, need - 1, headers)
    if info is None:
        raise SectionUnavailable("no segment index (sidx) in this file")
    plan = plan_segments(info, start, end)
    header = head[: info.sidx_start]
    total = len(header) + (plan.byte_end - plan.byte_start + 1)
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.ftruncate(fd, total)
        os.pwrite(fd, header, 0)
        spans = [(a, min(a + chunk - 1, plan.byte_end)) for a in range(plan.byte_start, plan.byte_end + 1, chunk)]
        done = [len(header)]
        lock = threading.Lock()

        def work(span):
            a, b = span
            data = _fetch(client, url, a, b, headers)
            os.pwrite(fd, data, len(header) + (a - plan.byte_start))
            with lock:
                done[0] += len(data)

        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(work, spans))
    finally:
        os.close(fd)
    return plan, done[0]


def download_section(video_url: str, audio_url: str | None, start: float, end: float, out: Path,
                     headers: dict | None = None, chunk: int = CHUNK_BYTES, workers: int = 12) -> SectionResult:
    """Download only [start, end] seconds (rounded out to segment boundaries) and write `out` (.mp4)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            vplan, vbytes = _fetch_part(client, video_url, start, end, d / "v.mp4", headers, chunk, workers)
            parts, abytes, astart = [d / "v.mp4"], 0, vplan.start_time
            if audio_url:
                aplan, abytes = _fetch_part(client, audio_url, start, end, d / "a.mp4", headers, chunk, workers)
                parts.append(d / "a.mp4")
                astart = aplan.start_time
        cmd = [ffmpeg_bin(), "-y", "-loglevel", "error"]
        for p in parts:
            cmd += ["-copyts", "-i", str(p)]
        cmd += ["-map", "0:v:0"] + (["-map", "1:a:0"] if audio_url else []) + ["-c", "copy", str(d / "joined.mp4")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"could not join the section: {r.stderr.strip()[-300:]}")
        r = subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(d / "joined.mp4"), "-c", "copy",
                            "-movflags", "+faststart", str(out)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"could not finish the section: {r.stderr.strip()[-300:]}")
    first = min(vplan.start_time, astart)
    last = max(vplan.end_time, vplan.end_time)
    return SectionResult(first, last - first, vbytes + abytes)
