import json
from pathlib import Path


class SaveStore:
    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).resolve().parent / "save_data.json")

    def load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}

    def save(self, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))

