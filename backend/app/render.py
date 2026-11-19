import subprocess
from pathlib import Path

from .config import ffmpeg_bin
from .layouts import Box, build_filter_complex


def render_clip(src: Path, out: Path, start: float, end: float, layout: str, game: Box,
                face: Box | None, src_w: int, src_h: int, ass_path: Path | None = None) -> None:
    fc = build_filter_complex(layout, game, face, src_w, src_h, ass_path)
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-i", str(src), "-filter_complex", fc, "-map", "[out]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-500:])
