import subprocess

from app.transcribe import transcribe


def test_transcribe_runs_on_audio_without_pyav_decode(tmp_path):
    p = tmp_path / "tone.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=4",
                    "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-shortest", str(p)], check=True)
    words = transcribe(p, 0, 4)
    assert isinstance(words, list)
