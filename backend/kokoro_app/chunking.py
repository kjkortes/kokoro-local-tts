from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+")


@dataclass(frozen=True)
class TextChunk:
    text: str
    pause_after_ms: int
    kind: Literal["sentence", "paragraph"]


def _split_oversized(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    parts: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current += f" {word}"
        else:
            parts.append(current)
            current = word
    parts.append(current)
    return parts


def chunk_script(text: str, max_chars: int = 420) -> list[TextChunk]:
    if max_chars < 16:
        raise ValueError("max_chars must be at least 16")
    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text)]
    paragraphs = [item for item in paragraphs if item]
    chunks: list[TextChunk] = []
    for paragraph in paragraphs:
        sentences = [item.strip() for item in _SENTENCE_BOUNDARY.split(paragraph) if item.strip()]
        parts: list[str] = []
        for sentence in sentences:
            parts.extend(_split_oversized(sentence, max_chars))
        for index, part in enumerate(parts):
            is_last = index == len(parts) - 1
            chunks.append(
                TextChunk(
                    text=part,
                    pause_after_ms=520 if is_last else 220,
                    kind="paragraph" if is_last else "sentence",
                )
            )
    return chunks
