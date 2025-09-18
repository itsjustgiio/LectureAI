
def chunk_text(text: str, max_chars: int = 1000):
    """
    Split text into chunks of up to max_chars characters.

    Args:
        text: the full text to split
        max_chars: maximum characters per chunk

    Returns:
        A list of text chunks.
    """
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)] or [text]