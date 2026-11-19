import json
from pathlib import Path


class ProfileStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "profiles.json"

    def _all(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, channel_id: str) -> dict | None:
        return self._all().get(channel_id)

    def save(self, channel_id: str, game: dict, face: dict | None) -> None:
        data = self._all()
        data[channel_id] = {"game": game, "face": face}
        self.path.write_text(json.dumps(data))
