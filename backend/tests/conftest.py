import subprocess

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import download, signals
from app.download import VideoInfo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path / "data"))
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    vid = tmp_path / "fake.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=d=40:s=320x180:r=10",
                    "-f", "lavfi", "-i", "sine=d=40", "-shortest", "-pix_fmt", "yuv420p", str(vid)], check=True)
    monkeypatch.setattr(download, "download_video", lambda url, d: VideoInfo(
        vid, "T", "UC1", "Chan", 40.0, 320, 180, {}))
    bump = np.zeros(40); bump[20:24] = 1
    monkeypatch.setattr(signals, "audio_energy", lambda p, d: bump)
    monkeypatch.setattr(signals, "chat_rate", lambda u, d: np.zeros(40))
    from app.main import app
    return TestClient(app)


