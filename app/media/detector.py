from pathlib import Path


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

DOCUMENT_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
}


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
}


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mpg",
    ".mpeg",
    ".mov",
    ".mkv",
    ".webm",
}


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def detect_file_type(file_path):
    """
    Detect the general category and format
    of a file.

    Returns:

        {
            "status": "success",
            "category": "document",
            "type": "pdf",
            "extension": ".pdf",
            "file_name": "example.pdf"
        }

    or an error dictionary.
    """

    path = Path(file_path)

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

    extension = path.suffix.lower()

    if extension in DOCUMENT_EXTENSIONS:
        category = "document"

    elif extension in IMAGE_EXTENSIONS:
        category = "image"

    elif extension in AUDIO_EXTENSIONS:
        category = "audio"

    elif extension in VIDEO_EXTENSIONS:
        category = "video"

    else:
        return {
            "status": "error",
            "error": (
                "Unsupported file type: "
                f"{extension or '[no extension]'}"
            ),
        }

    return {
        "status": "success",
        "category": category,
        "type": extension[1:],
        "extension": extension,
        "file_name": path.name,
    }


# ============================================================
# SUPPORTED FILE CHECK
# ============================================================

def is_supported_file(file_path):
    """
    Return True when the file format is supported.
    """

    result = detect_file_type(
        file_path
    )

    return result.get(
        "status"
    ) == "success"
