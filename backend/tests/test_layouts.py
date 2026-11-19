import re

import pytest

from app.layouts import LAYOUTS, Box, build_filter_complex

G = Box(0.0, 0.0, 0.7, 1.0)
F = Box(0.75, 0.05, 0.2, 0.3)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_filter_ends_with_out_label(layout):
    assert build_filter_complex(layout, G, F, 1280, 720, None).endswith("[out]")


def test_unknown_layout_raises():
    with pytest.raises(ValueError):
        build_filter_complex("nope", G, F, 1280, 720, None)


@pytest.mark.parametrize("layout", ["stacked", "bubble", "face_only"])
def test_face_layout_without_face_raises(layout):
    with pytest.raises(ValueError):
        build_filter_complex(layout, G, None, 1280, 720, None)


def test_game_only_needs_no_face():
    assert build_filter_complex("game_only", G, None, 1280, 720, None)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_crop_pixels_within_source(layout):
    edge = Box(0.9, 0.9, 0.2, 0.2)
    f = build_filter_complex(layout, edge, edge, 1280, 720, None)
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", f)
    assert crops
    for w, h, x, y in map(lambda t: tuple(map(int, t)), crops):
        assert w >= 2 and h >= 2 and x + w <= 1280 and y + h <= 720


def test_ass_filter_added():
    from pathlib import Path
    assert "ass=" in build_filter_complex("stacked", G, F, 1280, 720, Path("/tmp/a.ass"))


def test_box_clamped():
    b = Box(-0.5, 0.9, 2.0, 2.0).clamped()
    assert 0 <= b.x and b.x + b.w <= 1.0001 and b.y + b.h <= 1.0001
