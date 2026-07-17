import hashlib
import re


_WHITESPACE = re.compile(r"\s+")


def normalize_prompt(prompt: str) -> str:
    """Trim a prompt and make all runs of whitespace equivalent."""
    return _WHITESPACE.sub(" ", prompt.strip())


def prompt_id(normalized_prompt: str) -> str:
    return hashlib.sha256(normalized_prompt.encode("utf-8")).hexdigest()
