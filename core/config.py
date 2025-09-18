import os
import json
from pathlib import Path

# Base app directory (where app.py lives)
APP_DIR = Path(__file__).resolve().parents[1]

# Data and state files
DATA_DIR = APP_DIR / "data"
STATE_PATH = APP_DIR / "app_state.json"

# Make sure the data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- Load & Save State ---------------- #
def load_state():
    """Load app_state.json or return default if not found."""
    if STATE_PATH.exists():
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"classes": {}}  # default structure

def save_state(state: dict):
    """Save state to app_state.json."""
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ---------------- Directory Helpers ---------------- #
def ensure_class_dir(class_name: str):
    """Ensure class directory exists and return path."""
    d = DATA_DIR / class_name
    d.mkdir(parents=True, exist_ok=True)
    return d

def ensure_day_dir(class_name: str, day_label: str):
    """Ensure day directory inside a class exists and return path."""
    d = DATA_DIR / class_name / day_label
    d.mkdir(parents=True, exist_ok=True)
    return d

# ---------------- System Helpers ---------------- #
def is_windows():
    return os.name == "nt"

def open_in_explorer(path: str | Path):
    """Open folder in system file explorer."""
    path = str(path)
    try:
        if is_windows():
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            import platform
            if platform.system() == "Darwin":  # macOS
                os.system(f'open "{path}"')
            else:  # Linux
                os.system(f'xdg-open "{path}"')
    except Exception as e:
        print("Open folder error:", e)
