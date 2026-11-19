import subprocess

import pytest

from app import transcribe as t


@pytest.fixture
def tone(tmp_path):
    p = tmp_path / "tone.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=4",
                    "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-shortest", str(p)], check=True)
    return p


def test_backend_env_override(monkeypatch):
    monkeypatch.setenv("WHISPER_BACKEND", "faster")
    assert t.backend() == "faster"


def test_backend_prefers_mlx_on_apple_silicon_when_installed(monkeypatch):
    monkeypatch.delenv("WHISPER_BACKEND", raising=False)
    import platform
    expected = "mlx" if (platform.system() == "Darwin" and platform.machine() == "arm64") else "faster"
    assert t.backend() == expected


@pytest.mark.parametrize("backend", ["faster", "mlx"])
def test_transcribe_returns_words_list_on_both_backends(monkeypatch, tone, backend):
    monkeypatch.setenv("WHISPER_BACKEND", backend)
    assert isinstance(t.transcribe(tone, 0, 4), list)


@pytest.mark.parametrize("backend", ["faster", "mlx"])
def test_transcribe_text_returns_string_on_both_backends(monkeypatch, tone, backend):
    monkeypatch.setenv("WHISPER_BACKEND", backend)
    assert isinstance(t.transcribe_text(tone, 0, 4), str)


def test_mlx_words_are_mapped_to_word_objects(monkeypatch, tone):
    class FakeMLX:
        @staticmethod
        def transcribe(audio, **kw):
            assert kw["word_timestamps"] is True
            return {"text": " hi there", "segments": [{"words": [
                {"word": " hi", "start": 0.0, "end": 0.4}, {"word": " there", "start": 0.4, "end": 0.9}]}]}
    monkeypatch.setenv("WHISPER_BACKEND", "mlx")
    monkeypatch.setattr(t, "_mlx", lambda: FakeMLX)
    words = t.transcribe(tone, 0, 4)
    assert [(w.text.strip(), w.start, w.end) for w in words] == [("hi", 0.0, 0.4), ("there", 0.4, 0.9)]
