# core/services/summarizer.py

from ..utils.chunking import chunk_text  # helper to split long text

_summarizer = None  # lazy-loaded for speed

def _lazy_summarizer():
    """Import summarization pipeline only when needed (first call)."""
    global _summarizer
    if _summarizer is None:
        from transformers import pipeline  # type: ignore
        _summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    return _summarizer

def summarize_text(text: str, max_chunk: int = 1000, max_length: int = 150, min_length: int = 50) -> str:
    """
    Summarize long text by splitting into chunks and combining results.

    Args:
        text: the transcript text to summarize
        max_chunk: max characters per chunk
        max_length: max tokens in summary
        min_length: min tokens in summary

    Returns:
        A single summary string.
    """
    pipe = _lazy_summarizer()
    chunks = chunk_text(text, max_chars=max_chunk)

    outputs = []
    for chunk in chunks:
        result = pipe(chunk, max_length=max_length, min_length=min_length, do_sample=False)
        outputs.append(result[0]["summary_text"])

    return " ".join(outputs).strip()
