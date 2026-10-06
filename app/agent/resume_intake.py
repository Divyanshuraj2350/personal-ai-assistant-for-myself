from pathlib import Path
import uuid

from fastapi import UploadFile

from app.media.processor import (
    process_file,
    MediaProcessingError,
)


class ResumeIntakeError(Exception):
    """Raised when a resume cannot be accepted or processed."""
    pass


ALLOWED_RESUME_EXTENSIONS = {".pdf"}

UPLOAD_DIRECTORY = Path("data/uploads")


async def intake_resume(file: UploadFile):
    """
    Accept the user's original resume PDF, preserve it in the
    existing upload storage, and process it through the existing
    unified media pipeline.

    This function does NOT modify, rewrite, generate, or tailor
    the resume.
    """

    if not file.filename:
        raise ResumeIntakeError(
            "No resume file was selected."
        )

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()

    # ---------------------------------------------------------
    # Resume format validation
    # ---------------------------------------------------------

    if extension not in ALLOWED_RESUME_EXTENSIONS:
        raise ResumeIntakeError(
            "Career Assistant currently accepts resume files "
            "in PDF format only."
        )

    # ---------------------------------------------------------
    # Read uploaded file
    # ---------------------------------------------------------

    try:
        file_data = await file.read()
    except Exception as exc:
        raise ResumeIntakeError(
            f"Could not read the uploaded resume: {exc}"
        ) from exc

    if not file_data:
        raise ResumeIntakeError(
            "The uploaded resume is empty."
        )

    # ---------------------------------------------------------
    # Preserve original file
    # ---------------------------------------------------------

    UPLOAD_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_name = (
        f"{uuid.uuid4().hex}{extension}"
    )

    stored_path = (
        UPLOAD_DIRECTORY / stored_name
    )

    try:
        stored_path.write_bytes(file_data)
    except Exception as exc:
        raise ResumeIntakeError(
            f"Could not store the uploaded resume: {exc}"
        ) from exc

    # ---------------------------------------------------------
    # Process through existing media pipeline
    # ---------------------------------------------------------

    try:
        result = process_file(stored_path)

    except MediaProcessingError as exc:
        # Do not leave an apparently valid resume in the
        # Career workflow if processing failed.
        raise ResumeIntakeError(
            f"Resume processing failed: {exc}"
        ) from exc

    except Exception as exc:
        raise ResumeIntakeError(
            f"Unexpected resume processing error: {exc}"
        ) from exc

    # ---------------------------------------------------------
    # Validate processing result
    # ---------------------------------------------------------

    if not isinstance(result, dict):
        raise ResumeIntakeError(
            "Resume processor returned an invalid result."
        )

    if result.get("processing_status") != "completed":
        raise ResumeIntakeError(
            "Resume processing did not complete successfully."
        )

    if result.get("media_type") != "document":
        raise ResumeIntakeError(
            "Uploaded resume was not recognized as a document."
        )

    file_id = result.get("file_id")

    if not file_id:
        raise ResumeIntakeError(
            "Resume was processed but no file ID was created."
        )

    # ---------------------------------------------------------
    # Return Career-specific resume reference
    # ---------------------------------------------------------

    return {
        "status": "success",
        "file_id": file_id,
        "file_name": original_name,
        "file_path": result.get(
            "file_path",
            str(stored_path.resolve()),
        ),
        "media_type": result.get("media_type"),
        "processing_status": result.get(
            "processing_status"
        ),
        "processing_method": result.get(
            "processing_method"
        ),
        "rag_document_id": result.get(
            "document_id"
        ),
        "chunks": result.get(
            "total_chunks",
            result.get(
                "chunks_added",
                result.get(
                    "chunk_count",
                    0,
                ),
            ),
        ),
        "resume_source": "user_uploaded_original",
    }
