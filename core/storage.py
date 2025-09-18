from pathlib import Path
from datetime import datetime
import json

# ---------------- Save Transcript & Summary ---------------- #
def save_texts(day_dir: str | Path, transcript: str, summary: str):
    """
    Save transcript.txt and summary.txt inside the given day directory.
    """
    day_dir = Path(day_dir)
    (day_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    (day_dir / "summary.txt").write_text(summary, encoding="utf-8")

# ---------------- Save Metadata ---------------- #
def save_meta(day_dir: str | Path, audio_path: str, whisper_model: str):
    """
    Save meta.json containing audio path, model used, and timestamp.
    """
    day_dir = Path(day_dir)
    meta = {
        "audio_path": audio_path,
        "whisper_model": whisper_model,
        "transcribed_at": datetime.now().isoformat(timespec="seconds")
    }
    (day_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
