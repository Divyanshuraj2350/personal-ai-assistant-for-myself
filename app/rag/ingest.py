import re

from app.rag.store import (
    add_chunks,
    create_document_id,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_CHUNK_SIZE = 800

DEFAULT_CHUNK_OVERLAP = 100


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(
    text,
):
    """
    Clean text before storing it.

    This removes unnecessary whitespace
    while preserving the actual content.
    """

    if not isinstance(
        text,
        str,
    ):

        return ""

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    # Remove excessive spaces.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Limit excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# CHUNK TEXT
# ============================================================

def chunk_text(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_CHUNK_OVERLAP,
):

    """
    Split text into overlapping chunks.

    The chunker attempts to preserve natural
    boundaries where possible.
    """

    text = clean_text(
        text
    )

    if not text:
        return []

    if chunk_size <= 0:
        return [
            text
        ]

    if overlap < 0:
        overlap = 0

    if overlap >= chunk_size:
        overlap = 0

    chunks = []

    start = 0

    text_length = len(
        text
    )

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length,
        )

        # Try to avoid cutting a sentence
        # or word in the middle.
        if end < text_length:

            search_start = max(
                start,
                end - 200,
            )

            boundary = max(
                text.rfind(
                    "\n",
                    search_start,
                    end,
                ),
                text.rfind(
                    ". ",
                    search_start,
                    end,
                ),
                text.rfind(
                    "? ",
                    search_start,
                    end,
                ),
                text.rfind(
                    "! ",
                    search_start,
                    end,
                ),
                text.rfind(
                    " ",
                    search_start,
                    end,
                ),
            )

            if boundary > start:
                end = boundary + 1

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        # Move forward while preserving overlap.
        start = max(
            end - overlap,
            start + 1,
        )

    return chunks


# ============================================================
# INGEST TEXT
# ============================================================

def ingest_text(
    text,
    source="manual",
    metadata=None,
    document_id=None,
):
    """
    Full ingestion pipeline for text.

    Pipeline:

    Text
      ↓
    Clean
      ↓
    Create Document ID
      ↓
    Chunk
      ↓
    Embed
      ↓
    Store in ChromaDB
    """

    cleaned_text = clean_text(
        text
    )

    if not cleaned_text:

        return {
            "status": "error",
            "error": "No valid text to ingest.",
        }
    if document_id is None:
        document_id = create_document_id(
            cleaned_text
        )

    chunks = chunk_text(
        cleaned_text
    )

    if metadata is None:

        metadata = {}

    document_metadata = {
        **metadata,
        "source": source,
    }

    result = add_chunks(
        document_id=document_id,
        chunks=chunks,
        metadata=document_metadata,
    )

    result["source"] = source

    result["total_chunks"] = len(
        chunks
    )

    return result