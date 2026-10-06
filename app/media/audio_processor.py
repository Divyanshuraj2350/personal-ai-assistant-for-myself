import os
import re
import subprocess
from pathlib import Path

from app.voice.stt import (
    WHISPER_CLI,
    WHISPER_MODEL,
    VAD_MODEL,
    transcribe_file,
    STTError,
)

from app.rag.ingest import ingest_text


SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
}


# ============================================================
# AUDIO PROCESSING
# ============================================================

def process_audio(audio_path):
    """
    Transcribe a supported audio file using the existing
    local Whisper STT implementation.
    """

    path = Path(audio_path).expanduser().resolve()

    if not path.exists():
        return {
            "status": "error",
            "error": "Audio file does not exist.",
        }

    if not path.is_file():
        return {
            "status": "error",
            "error": "Path is not a file.",
        }

    extension = path.suffix.lower()

    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        return {
            "status": "error",
            "error": (
                f"Unsupported audio format: {extension}"
            ),
        }

    try:
        result = transcribe_file(
            str(path)
        )

    except STTError as error:
        return {
            "status": "error",
            "error": str(error),
        }

    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }

    text = result.get(
        "text",
        "",
    ).strip()

    if not text:
        return {
            "status": "empty",
            "file": path.name,
            "message": (
                "No speech could be transcribed "
                "from the audio."
            ),
        }

    return {
        "status": "success",
        "file": path.name,
        "file_path": str(path),
        "file_extension": extension,
        "media_type": "audio",
        "processing_method": "whisper",
        "language": result.get(
            "language",
            "auto",
        ),
        "text": text,
        "characters": len(text),
    }


# ============================================================
# AUDIO → RAG
# ============================================================

def ingest_audio(audio_path):
    """
    Transcribe an audio file and ingest the resulting
    transcript into the existing RAG pipeline.
    """

    path = Path(audio_path).expanduser().resolve()

    result = process_audio(
        audio_path
    )

    if result.get("status") != "success":
        return result

    text = result["text"]

    metadata = {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_path": str(path),
        "media_type": "audio",
        "processing_method": "whisper",
        "language": result.get(
            "language",
            "auto",
        ),
    }

    rag_result = ingest_text(
        text=text,
        source="audio",
        metadata=metadata,
    )

    return {
        **rag_result,
        "file": path.name,
        "media_type": "audio",
        "characters": len(text),
        "text": text,
    }


# ============================================================
# TIMESTAMP PARSING
# ============================================================

TIMESTAMP_PATTERN = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
    r"\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\]"
    r"\s*(.*)"
)


def timestamp_to_seconds(
    hours,
    minutes,
    seconds,
    milliseconds,
):
    """
    Convert Whisper timestamp components into seconds.
    """

    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


def parse_timestamped_output(output):
    """
    Parse Whisper timestamped stdout.

    Expected format:

    [00:00:00.000 --> 00:00:05.500]
    Text
    """

    segments = []

    lines = output.splitlines()

    current_start = None
    current_end = None
    current_text = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        match = TIMESTAMP_PATTERN.match(
            line
        )

        if match:

            if (
                current_start is not None
                and current_text
            ):
                segments.append(
                    {
                        "start": current_start,
                        "end": current_end,
                        "text": " ".join(
                            current_text
                        ).strip(),
                    }
                )

            current_start = timestamp_to_seconds(
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )

            current_end = timestamp_to_seconds(
                match.group(5),
                match.group(6),
                match.group(7),
                match.group(8),
            )

            text = match.group(9).strip()

            current_text = []

            if text:
                current_text.append(text)

            continue

        # Ignore Whisper diagnostic output.
        if (
            line.startswith("whisper_")
            or line.startswith("main:")
            or line.startswith("system_info:")
            or line.startswith("ggml_")
            or line.startswith("output_")
            or line.startswith("read_audio")
        ):
            continue

        if current_start is not None:
            current_text.append(line)

    if (
        current_start is not None
        and current_text
    ):
        segments.append(
            {
                "start": current_start,
                "end": current_end,
                "text": " ".join(
                    current_text
                ).strip(),
            }
        )

    return segments


# ============================================================
# TIMESTAMPED WHISPER
# ============================================================

def process_audio_with_timestamps(
    audio_path,
):
    """
    Transcribe audio using Whisper while preserving
    timestamp information.
    """

    path = Path(audio_path).expanduser().resolve()

    if not path.exists():
        return {
            "status": "error",
            "error": "Audio file does not exist.",
        }

    if not path.is_file():
        return {
            "status": "error",
            "error": "Path is not a file.",
        }

    extension = path.suffix.lower()

    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        return {
            "status": "error",
            "error": (
                f"Unsupported audio format: {extension}"
            ),
        }

    if not Path(WHISPER_CLI).exists():
        return {
            "status": "error",
            "error": (
                f"whisper-cli not found: "
                f"{WHISPER_CLI}"
            ),
        }

    if not Path(WHISPER_MODEL).exists():
        return {
            "status": "error",
            "error": (
                f"Whisper model not found: "
                f"{WHISPER_MODEL}"
            ),
        }

    command = [
        WHISPER_CLI,
        "-m",
        WHISPER_MODEL,
        "-f",
        str(path),
        "-l",
        "auto",
        "-np",
    ]

    if Path(VAD_MODEL).exists():
        command.extend(
            [
                "--vad",
                "-vm",
                VAD_MODEL,
            ]
        )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
        )

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": (
                "Whisper transcription timed out."
            ),
        }

    except OSError as error:
        return {
            "status": "error",
            "error": str(error),
        }

    if result.returncode != 0:

        error = result.stderr.strip()

        if not error:
            error = result.stdout.strip()

        return {
            "status": "error",
            "error": f"Whisper failed: {error}",
        }

    segments = parse_timestamped_output(
        result.stdout
    )

    if not segments:
        return {
            "status": "empty",
            "file": path.name,
            "message": (
                "Whisper did not produce "
                "timestamped speech segments."
            ),
        }

    transcript = " ".join(
        segment["text"]
        for segment in segments
    ).strip()

    return {
        "status": "success",
        "file": path.name,
        "file_path": str(path),
        "file_extension": extension,
        "media_type": "audio",
        "processing_method": "whisper_timestamped",
        "language": "auto",
        "text": transcript,
        "characters": len(transcript),
        "segments": segments,
    }

# ============================================================
# TIMESTAMP-AWARE CHUNKING
# ============================================================

DEFAULT_TIMESTAMP_CHUNK_SIZE = 800


def chunk_timestamped_segments(
    segments,
    max_chars=DEFAULT_TIMESTAMP_CHUNK_SIZE,
):
    """
    Combine Whisper timestamped segments into RAG-friendly
    chunks while preserving the timestamp range.

    Each returned chunk contains:

        {
            "start": float,
            "end": float,
            "text": str
        }

    The text length is kept close to max_chars whenever
    possible.
    """

    if not isinstance(segments, list):
        return []

    if max_chars <= 0:
        return []

    chunks = []

    current_text_parts = []
    current_start = None
    current_end = None
    current_length = 0

    for segment in segments:

        if not isinstance(segment, dict):
            continue

        text = str(
            segment.get("text", "")
        ).strip()

        if not text:
            continue

        start = segment.get("start")
        end = segment.get("end")

        if start is None or end is None:
            continue

        # ----------------------------------------------------
        # Estimate size if this segment is added.
        # ----------------------------------------------------

        separator_length = (
            1 if current_text_parts else 0
        )

        proposed_length = (
            current_length
            + separator_length
            + len(text)
        )

        # ----------------------------------------------------
        # If adding this segment would exceed the target,
        # finalize the current chunk first.
        # ----------------------------------------------------

        if (
            current_text_parts
            and proposed_length > max_chars
        ):
            chunks.append(
                {
                    "start": current_start,
                    "end": current_end,
                    "text": " ".join(
                        current_text_parts
                    ).strip(),
                }
            )

            current_text_parts = []
            current_start = None
            current_end = None
            current_length = 0

        # ----------------------------------------------------
        # Start a new chunk.
        # ----------------------------------------------------

        if current_start is None:
            current_start = float(start)

        current_end = float(end)

        current_text_parts.append(text)

        current_length = (
            sum(
                len(part)
                for part in current_text_parts
            )
            + max(
                0,
                len(current_text_parts) - 1,
            )
        )

    # --------------------------------------------------------
    # Final chunk.
    # --------------------------------------------------------

    if current_text_parts:

        chunks.append(
            {
                "start": current_start,
                "end": current_end,
                "text": " ".join(
                    current_text_parts
                ).strip(),
            }
        )

    return chunks


# ============================================================
# TIMESTAMPED AUDIO → RAG
# ============================================================

def ingest_audio_with_timestamps(
    audio_path,
):
    """
    Transcribe audio with timestamps, intelligently group
    timestamped segments, and ingest them into RAG.
    """

    path = Path(audio_path).expanduser().resolve()

    result = process_audio_with_timestamps(
        audio_path
    )

    if result.get("status") != "success":
        return result

    segments = result.get(
        "segments",
        [],
    )

    if not segments:
        return {
            "status": "empty",
            "file": path.name,
            "message": (
                "No timestamped transcript "
                "segments were produced."
            ),
        }

    # --------------------------------------------------------
    # Build timestamp-aware RAG chunks.
    # --------------------------------------------------------

    chunks = chunk_timestamped_segments(
        segments,
        max_chars=800,
    )

    if not chunks:
        return {
            "status": "empty",
            "file": path.name,
            "message": (
                "No valid timestamp-aware "
                "RAG chunks were produced."
            ),
        }

    # --------------------------------------------------------
    # Convert chunks into text for the existing RAG
    # ingestion pipeline.
    # --------------------------------------------------------

    rag_chunks = []

    for chunk in chunks:

        timestamp = (
            f"[{format_timestamp(chunk['start'])} - "
            f"{format_timestamp(chunk['end'])}]"
        )

        rag_chunks.append(
            f"{timestamp}\n"
            f"{chunk['text']}"
        )

    full_text = "\n\n".join(
        rag_chunks
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_path": str(path),
        "media_type": "audio",
        "processing_method": "whisper_timestamped",
        "language": result.get(
            "language",
            "auto",
        ),
        "timestamped": True,
    }

    # --------------------------------------------------------
    # Existing RAG ingestion.
    # --------------------------------------------------------

    rag_result = ingest_text(
        text=full_text,
        source="audio",
        metadata=metadata,
    )

    return {
        **rag_result,
        "file": path.name,
        "media_type": "audio",
        "timestamped": True,
        "segments": segments,
        "chunks": chunks,
        "text": result.get(
            "text",
            "",
        ),
    }

# ============================================================
# TIMESTAMP FORMATTING
# ============================================================

def format_timestamp(
    seconds,
):
    """
    Convert seconds into HH:MM:SS format.
    """

    total_seconds = int(
        seconds
    )

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    remaining_seconds = (
        total_seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining_seconds:02d}"
    )