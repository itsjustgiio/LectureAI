# core/services/transcriber.py

_whisper = None  # lazy-loaded so the app starts fast

def _lazy_whisper():
    """Import whisper only when needed (first call)."""
    global _whisper
    if _whisper is None:
        import whisper  # type: ignore
        _whisper = whisper
    return _whisper

def transcribe_file(audio_path: str, model_name: str = "small") -> str:
    """
    Transcribe an audio file using Whisper.
    
    Args:
        audio_path: path to the audio file (.mp3, .wav, .m4a, etc.)
        model_name: whisper model size ("tiny", "base", "small", "medium", "large")

    Returns:
        The transcribed text as a string.
    """
    whisper = _lazy_whisper()
    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path)
    return result.get("text", "").strip()
