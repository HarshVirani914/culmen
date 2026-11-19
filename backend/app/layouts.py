from dataclasses import dataclass
from pathlib import Path

LAYOUTS = ("stacked", "bubble", "game_only", "face_only")
W, H = 1080, 1920
MIN = 0.02


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    def clamped(self) -> "Box":
        x = min(max(self.x, 0.0), 1.0 - MIN)
        y = min(max(self.y, 0.0), 1.0 - MIN)
        w = min(max(self.w, MIN), 1.0 - x)
        h = min(max(self.h, MIN), 1.0 - y)
        return Box(x, y, w, h)


def _crop(box: Box, sw: int, sh: int) -> str:
    b = box.clamped()
    x, y = int(b.x * sw) // 2 * 2, int(b.y * sh) // 2 * 2
    w = max(2, int(b.w * sw) // 2 * 2)
    h = max(2, int(b.h * sh) // 2 * 2)
    w, h = min(w, (sw - x) // 2 * 2), min(h, (sh - y) // 2 * 2)
    return f"crop={max(w, 2)}:{max(h, 2)}:{x}:{y}"


def _cover(box: Box, sw: int, sh: int, tw: int, th: int) -> str:
    return f"{_crop(box, sw, sh)},scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"


def _esc(p: Path) -> str:
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_filter_complex(layout: str, game: Box, face: Box | None, src_w: int, src_h: int,
                         ass_path: Path | None) -> str:
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout: {layout}")
    if layout != "game_only" and face is None:
        raise ValueError(f"layout {layout} needs a facecam box")
    g = lambda tw, th: _cover(game, src_w, src_h, tw, th)  # noqa: E731
    if layout == "stacked":
        body = (f"[0:v]split=2[a][b];[a]{_cover(face, src_w, src_h, W, 700)}[f];"
                f"[b]{g(W, 1220)}[g];[f][g]vstack=inputs=2[v0]")
    elif layout == "bubble":
        body = (f"[0:v]split=2[a][b];[a]{g(W, H)}[g];[b]{_cover(face, src_w, src_h, 380, 380)}[f];"
                f"[g][f]overlay=40:1380[v0]")
    elif layout == "game_only":
        body = (f"[0:v]{_crop(game, src_w, src_h)},split=2[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20[bg];"
                f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]")
    else:
        body = f"[0:v]{_cover(face, src_w, src_h, W, H)}[v0]"
    tail = f"[v0]ass=filename='{_esc(ass_path)}'[out]" if ass_path else "[v0]null[out]"
    return f"{body};{tail}"
