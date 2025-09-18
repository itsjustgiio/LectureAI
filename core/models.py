from dataclasses import dataclass, asdict
from datetime import datetime
import json

@dataclass
class Meta:
    audio_path: str
    whisper_model: str
    transcribed_at: str

    def to_dict(self):
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

# Helper to create a new Meta object
def make_meta(audio_path: str, whisper_model: str) -> Meta:
    return Meta(
        audio_path=audio_path,
        whisper_model=whisper_model,
        transcribed_at=datetime.now().isoformat(timespec="seconds"),
    )
