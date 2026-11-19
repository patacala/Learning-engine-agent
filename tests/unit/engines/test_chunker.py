from learning_engine.engines.knowledge.chunker import (
    CHUNK_TARGET_TOKENS,
    chunk_document,
    count_tokens,
)


def test_empty_document_returns_no_chunks():
    assert chunk_document("") == []
    assert chunk_document("   \n  ") == []


def test_short_section_with_header_stays_as_one_chunk():
    content = "## Business Hours\n\nSaturday: 9:00 am - 6:00 pm\n\nSunday: Closed"
    chunks = chunk_document(content)
    assert len(chunks) == 1
    assert "## Business Hours" in chunks[0]
    assert "Saturday: 9:00 am - 6:00 pm" in chunks[0]


def test_oversized_section_is_sub_split_with_shared_header():
    header = "## Vehicle Specs"
    # One long line per "spec" so the section clearly exceeds CHUNK_TARGET_TOKENS.
    body = "\n".join(
        f"Spec line {i}: some detail about the vehicle feature {i}." for i in range(400)
    )
    content = f"{header}\n\n{body}"
    assert count_tokens(content) > CHUNK_TARGET_TOKENS

    chunks = chunk_document(content)
    assert len(chunks) > 1
    # Every sub-chunk carries the section header so a lone fragment doesn't
    # lose which section it belongs to.
    for c in chunks:
        assert header in c

    # Overlap: some text from the end of chunk N should reappear near the
    # start of chunk N+1.
    tail_of_first = chunks[0][-40:]
    assert tail_of_first[-15:] in chunks[1] or any(
        word in chunks[1] for word in tail_of_first.split() if len(word) > 4
    )


def test_document_without_headers_is_treated_as_one_section():
    content = "Just a plain paragraph with no markdown headers at all."
    chunks = chunk_document(content)
    assert chunks == [content]


def test_tiny_trailing_fragment_merges_into_previous_chunk():
    header = "## Notes"
    body = "\n".join(f"Line {i} with enough words to matter here." for i in range(300))
    content = f"{header}\n\n{body}\n\nend"
    chunks = chunk_document(content)
    # No chunk should be a near-empty leftover fragment.
    for c in chunks:
        assert count_tokens(c) >= 5
