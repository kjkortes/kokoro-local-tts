from kokoro_app.chunking import chunk_script


def test_chunking_preserves_text_and_paragraph_pause() -> None:
    chunks = chunk_script("First sentence. Second one!\n\nA new paragraph.", max_chars=24)
    assert " ".join(chunk.text for chunk in chunks) == "First sentence. Second one! A new paragraph."
    assert any(chunk.kind == "paragraph" and chunk.pause_after_ms > 400 for chunk in chunks)


def test_oversized_sentence_splits_on_words() -> None:
    chunks = chunk_script("word " * 150, max_chars=80)
    assert all(len(chunk.text) <= 80 for chunk in chunks)


def test_blank_script_has_no_chunks() -> None:
    assert chunk_script(" \n\n ") == []
