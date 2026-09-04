from pathlib import Path

from app.rag.ingest import ingest_text


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".txt",
}


# ============================================================
# READ TEXT FILE
# ============================================================

def extract_text_from_txt(
    file_path,
):
    """
    Extract text from a TXT file.
    """

    path = Path(
        file_path
    )

    if not path.exists():

        return {
            "status": "error",
            "error": "File does not exist.",
        }

    if not path.is_file():

        return {
            "status": "error",
            "error": "Path is not a file.",
        }

    try:

        text = path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return {
            "status": "error",
            "error": (
                "The TXT file is not "
                "UTF-8 encoded."
            ),
        }

    except OSError as error:

        return {
            "status": "error",
            "error": str(
                error
            ),
        }

    if not text.strip():

        return {
            "status": "error",
            "error": "The TXT file is empty.",
        }

    return {
        "status": "success",
        "text": text,
    }


# ============================================================
# INGEST TXT FILE
# ============================================================

def ingest_txt_file(
    file_path,
):
    """
    Extract text from a TXT file and send it
    through the normal RAG ingestion pipeline.
    """

    extraction = extract_text_from_txt(
        file_path
    )

    if extraction.get(
        "status"
    ) != "success":

        return extraction

    path = Path(
        file_path
    )

    metadata = {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_path": str(
            path
        ),
    }

    return ingest_text(
        text=extraction["text"],
        source="txt_file",
        metadata=metadata,
    )


# ============================================================
# GENERAL FILE INGESTION
# ============================================================

def ingest_file(
    file_path,
):
    """
    Detect the file type and send it to the
    correct ingestion function.

    More file types will be added later.
    """

    path = Path(
        file_path
    )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:

        return {
            "status": "error",
            "error": (
                "Unsupported file type: "
                f"{extension}"
            ),
        }

    if extension == ".txt":

        return ingest_txt_file(
            file_path
        )

    return {
        "status": "error",
        "error": "Could not determine file type.",
    }