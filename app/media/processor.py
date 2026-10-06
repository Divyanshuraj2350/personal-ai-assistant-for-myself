from pathlib import Path

from app.media.detector import detect_file_type
from app.media.document_processor import ingest_document
from app.rag.image_ingest import ingest_image
from app.media.audio_processor import ingest_audio_with_timestamps
from app.media.video_processor import ingest_video_with_rag

from app.media.file_registry import (
    FileRegistryError,
    create_file_record,
    get_file_record_by_path,
    update_file_record,
)


class MediaProcessingError(Exception):
    """Raised when a media file cannot be processed."""
    pass


def process_file(file_path):
    """
    Unified entry point for supported media files.

    Detects the file type, tracks the file in the persistent
    registry, and routes it to the appropriate processor.
    """

    path = Path(file_path)

    if not path.exists():
        raise MediaProcessingError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise MediaProcessingError(
            f"Path is not a file: {path}"
        )

    path = path.resolve()

    # --------------------------------------------------------
    # File type detection
    # --------------------------------------------------------

    try:
        detection = detect_file_type(path)

        if not isinstance(detection, dict):
            raise MediaProcessingError(
                "File detector returned an invalid result."
            )

        if detection.get("status") != "success":
            raise MediaProcessingError(
                detection.get(
                    "error",
                    "File type detection failed.",
                )
            )

        media_type = detection.get("category")

    except MediaProcessingError:
        raise

    except Exception as exc:
        raise MediaProcessingError(
            f"Could not detect file type: {exc}"
        ) from exc

    # --------------------------------------------------------
    # File registry
    # --------------------------------------------------------

    try:
        record = get_file_record_by_path(path)

        if record is None:
            record = create_file_record(
                file_path=path,
                media_type=media_type,
                processing_status="pending",
            )

        file_id = record["file_id"]

        update_file_record(
            file_id=file_id,
            processing_status="processing",
        )

    except FileRegistryError as exc:
        raise MediaProcessingError(
            f"File registry error: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Processing
    # --------------------------------------------------------

    try:

        if media_type == "document":
            result = ingest_document(path)

        elif media_type == "image":
            result = ingest_image(path)

        elif media_type == "audio":
            result = ingest_audio_with_timestamps(path)

        elif media_type == "video":
            result = ingest_video_with_rag(path)

        else:
            raise MediaProcessingError(
                f"Unsupported media type: {media_type}"
            )

    except Exception as exc:

        try:
            update_file_record(
                file_id=file_id,
                processing_status="failed",
            )
        except Exception:
            pass

        raise MediaProcessingError(
            f"Media processing failed: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Validate processor result
    # --------------------------------------------------------

    if not isinstance(result, dict):

        try:
            update_file_record(
                file_id=file_id,
                processing_status="failed",
            )
        except Exception:
            pass

        raise MediaProcessingError(
            "Processor returned an invalid result."
        )

    # --------------------------------------------------------
    # Extract processing information
    # --------------------------------------------------------

    processing_method = result.get(
        "processing_method"
    )

    rag_document_id = result.get(
        "document_id"
    )

    # --------------------------------------------------------
    # Update registry
    # --------------------------------------------------------

    try:

        update_file_record(
            file_id=file_id,
            processing_status="completed",
            processing_method=processing_method,
            rag_document_id=rag_document_id,
        )

    except FileRegistryError as exc:

        raise MediaProcessingError(
            f"Could not update file registry: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Unified result
    # --------------------------------------------------------

    result.setdefault(
        "file_name",
        path.name,
    )

    result.setdefault(
        "file_path",
        str(path),
    )

    result.setdefault(
        "media_type",
        media_type,
    )

    result["file_id"] = file_id

    result["processing_status"] = "completed"

    return result