import json
import subprocess

import pytest

from app.layouts import LAYOUTS, Box
from app.render import render_clip


def probe(p):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def src(tmp_path_factory):
    p = tmp_path_factory.mktemp("s") / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=d=5:s=1280x720:r=30",
                    "-f", "lavfi", "-i", "sine=d=5", "-shortest", "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


@pytest.mark.parametrize("layout", LAYOUTS)
def test_render_produces_1080x1920_mp4(src, tmp_path, layout):
    out = tmp_path / "o.mp4"
    render_clip(src, out, 1, 4, layout, Box(0, 0, 0.7, 1), Box(0.75, 0.05, 0.2, 0.3), 1280, 720)
    info = probe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["codec_name"]) == (1080, 1920, "h264")
    assert abs(float(info["format"]["duration"]) - 3) < 0.5


@pytest.mark.parametrize("layout", LAYOUTS)
def test_render_with_ass_captions_and_spaces_in_path(src, tmp_path, layout):
    from app.captions import Word, build_ass
    d = tmp_path / "dir with space"
    d.mkdir()
    ass = d / "c.ass"
    build_ass([Word("hello", 0, 0.5), Word("world", 0.5, 1.0)], ass, credit="Source: Chan", clip_len=3)
    out = tmp_path / "o.mp4"
    render_clip(src, out, 1, 4, layout, Box(0, 0, 0.7, 1), Box(0.75, 0.05, 0.2, 0.3), 1280, 720, ass)
    v = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)


def test_render_uses_quality_preset(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app import render
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr(render.subprocess, "run", fake_run)
    render.render_clip(tmp_path / "s.mp4", tmp_path / "o.mp4", 0, 5, "game_only", Box(0, 0, 1, 1), None, 1280, 720)
    cmd = seen["cmd"]
    assert cmd[cmd.index("-preset") + 1] == "medium"
    assert cmd[cmd.index("-crf") + 1] == "18"
