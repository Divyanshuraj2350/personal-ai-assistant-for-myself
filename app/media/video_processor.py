import os
import json
import subprocess
import hashlib
from pathlib import Path

from app.media.detector import detect_file_type, is_supported_file
from app.voice.stt import transcribe_audio
from app.media.audio_processor import (
    process_audio_with_timestamps,
    chunk_timestamped_segments,
    format_timestamp,
)
from app.rag.ingest import ingest_text


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mpg",
    ".mpeg",
    ".mov",
    ".mkv",
    ".webm",
}


class VideoProcessingError(Exception):
    """Raised when video processing fails."""


def _run_ffprobe(video_path):
    """
    Read video metadata using ffprobe.
    """

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_streams",
        "-of",
        "json",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise VideoProcessingError(
            "ffprobe was not found. Make sure FFmpeg is installed."
        )
    except subprocess.CalledProcessError as exc:
        raise VideoProcessingError(
            f"ffprobe failed: {exc.stderr.strip()}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise VideoProcessingError("Could not parse ffprobe output.")


def get_video_metadata(video_path):
    """
    Return basic metadata about a video.
    """

    video_path = Path(video_path).expanduser().resolve()

    if not video_path.exists():
        raise VideoProcessingError(
            f"Video file does not exist: {video_path}"
        )

    if not video_path.is_file():
        raise VideoProcessingError(
            f"Path is not a file: {video_path}"
        )

    extension = video_path.suffix.lower()

    if extension not in VIDEO_EXTENSIONS:
        raise VideoProcessingError(
            f"Unsupported video format: {extension}"
        )

    metadata = _run_ffprobe(video_path)

    duration = metadata.get("format", {}).get("duration")

    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    streams = metadata.get("streams", [])

    video_stream = None
    audio_stream = None

    for stream in streams:
        codec_type = stream.get("codec_type")

        if codec_type == "video" and video_stream is None:
            video_stream = stream

        elif codec_type == "audio" and audio_stream is None:
            audio_stream = stream

    return {
        "file_name": video_path.name,
        "file_extension": extension,
        "file_path": str(video_path),
        "media_type": "video",
        "duration": duration,
        "has_video": video_stream is not None,
        "has_audio": audio_stream is not None,
        "video_codec": (
            video_stream.get("codec_name")
            if video_stream
            else None
        ),
        "audio_codec": (
            audio_stream.get("codec_name")
            if audio_stream
            else None
        ),
    }


def extract_audio(video_path, output_dir=None):
    """
    Extract mono 16 kHz WAV audio from a video using FFmpeg.
    """

    video_path = Path(video_path).expanduser().resolve()

    metadata = get_video_metadata(video_path)

    if not metadata["has_audio"]:
        raise VideoProcessingError(
            "Video does not contain an audio stream."
        )

    if output_dir is None:
        output_dir = video_path.parent / "extracted_audio"
    else:
        output_dir = Path(output_dir).expanduser().resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{video_path.stem}_audio.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise VideoProcessingError(
            "FFmpeg was not found. Make sure FFmpeg is installed."
        )

    if result.returncode != 0:
        raise VideoProcessingError(
            f"FFmpeg audio extraction failed:\n{result.stderr}"
        )

    if not output_path.exists():
        raise VideoProcessingError(
            "FFmpeg completed but the extracted audio file was not created."
        )

    return str(output_path)


def process_video(video_path, output_dir=None):
    """
    Validate, inspect, and extract audio from a video.

    This phase does NOT perform transcription yet.
    """

    video_path = Path(video_path).expanduser().resolve()

    try:
        metadata = get_video_metadata(video_path)

        audio_path = extract_audio(
            video_path,
            output_dir=output_dir,
        )

        return {
            "status": "success",
            **metadata,
            "audio_path": audio_path,
            "processing_method": "ffmpeg",
        }

    except VideoProcessingError as exc:
        return {
            "status": "error",
            "file_name": video_path.name,
            "media_type": "video",
            "error": str(exc),
        }


def is_video_file(video_path):
    """
    Check whether a path is a supported video file.
    """

    try:
        file_type = detect_file_type(video_path)
        return file_type == "video"
    except Exception:
        return False

def process_video_with_transcription(video_path, output_dir=None):
    """
    Extract audio from a video and transcribe it
    using the existing Whisper STT pipeline.
    """

    video_path = Path(video_path).expanduser().resolve()

    try:
        video_result = process_video(
            video_path,
            output_dir=output_dir,
        )

        if video_result["status"] != "success":
            return video_result

        audio_path = video_result["audio_path"]

        transcription = transcribe_audio(
            audio_path,
            language="auto",
            use_vad=True,
        )

        return {
            **video_result,
            "transcript": transcription.get("text", ""),
            "language": transcription.get("language", "auto"),
            "processing_method": "ffmpeg+whisper",
        }

    except Exception as exc:
        return {
            "status": "error",
            "file_name": video_path.name,
            "media_type": "video",
            "error": str(exc),
        }

def process_video_with_timestamps(video_path, output_dir=None):
    """
    Extract audio from a video and produce a timestamped
    transcript using the existing audio timestamp pipeline.
    """

    video_path = Path(video_path).expanduser().resolve()

    try:
        video_result = process_video(
            video_path,
            output_dir=output_dir,
        )

        if video_result["status"] != "success":
            return video_result

        audio_path = video_result["audio_path"]

        audio_result = process_audio_with_timestamps(
            audio_path
        )

        if audio_result["status"] != "success":
            return {
                **video_result,
                "status": audio_result["status"],
                "error": audio_result.get(
                    "error",
                    audio_result.get("message", "Audio transcription failed."),
                ),
            }

        return {
            **video_result,
            "status": "success",
            "processing_method": "ffmpeg+whisper_timestamped",
            "language": audio_result["language"],
            "text": audio_result["text"],
            "characters": audio_result["characters"],
            "segments": audio_result["segments"],
            "timestamped": True,
        }

    except Exception as exc:
        return {
            "status": "error",
            "file_name": video_path.name,
            "media_type": "video",
            "error": str(exc),
        }

def process_video_with_chunks(
    video_path,
    output_dir=None,
    max_chars=800,
):
    """
    Process a video into timestamp-aware RAG-friendly chunks.

    Pipeline:
        Video
        -> FFmpeg audio extraction
        -> Whisper timestamped transcription
        -> timestamp-aware chunking
    """

    video_path = Path(video_path).expanduser().resolve()

    try:
        timestamp_result = process_video_with_timestamps(
            video_path,
            output_dir=output_dir,
        )

        if timestamp_result["status"] != "success":
            return timestamp_result

        chunks = chunk_timestamped_segments(
            timestamp_result["segments"],
            max_chars=max_chars,
        )

        if not chunks:
            return {
                **timestamp_result,
                "status": "empty",
                "chunks": [],
                "chunk_count": 0,
                "message": (
                    "No timestamp-aware chunks were created."
                ),
            }

        return {
            **timestamp_result,
            "processing_method": (
                "ffmpeg+whisper_timestamped+chunking"
            ),
            "chunks": chunks,
            "chunk_count": len(chunks),
        }

    except Exception as exc:
        return {
            "status": "error",
            "file_name": video_path.name,
            "media_type": "video",
            "error": str(exc),
        }

def ingest_video_with_rag(
    video_path,
    output_dir=None,
    max_chars=800,
):
    """
    Process a video and ingest its timestamp-aware
    transcript into the existing RAG system.

    Pipeline:

        Video
          ↓
        FFmpeg
          ↓
        Whisper timestamped transcription
          ↓
        Timestamp-aware chunking
          ↓
        Existing RAG ingestion
    """

    video_path = Path(video_path).expanduser().resolve()

    try:
        result = process_video_with_chunks(
            video_path,
            output_dir=output_dir,
            max_chars=max_chars,
        )

        if result["status"] != "success":
            return result

        chunks = result.get("chunks", [])

        if not chunks:
            return {
                **result,
                "status": "empty",
                "error": "No timestamp-aware chunks available.",
            }

        # ----------------------------------------------------
        # Build timestamp-aware RAG text.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        metadata = {
            "file_name": result["file_name"],
            "file_extension": result["file_extension"],
            "file_path": result["file_path"],
            "media_type": "video",
            "processing_method": (
                "ffmpeg+whisper_timestamped"
            ),
            "language": result.get(
                "language",
                "auto",
            ),
            "timestamped": True,
            "duration": result.get(
                "duration"
            ),
            "video_codec": result.get(
                "video_codec"
            ),
            "audio_codec": result.get(
                "audio_codec"
            ),
        }

        # ----------------------------------------------------
        # Existing RAG ingestion.
        # ----------------------------------------------------
        source_identity = (
            f"video:{Path(result['file_path']).resolve()}:{full_text}"
        )

        document_id = hashlib.sha256(
            source_identity.encode("utf-8")
        ).hexdigest()

        rag_result = ingest_text(
            text=full_text,
            source="video",
            metadata=metadata,
            document_id=document_id,
        )

        return {
            **rag_result,
            "file": result["file_name"],
            "media_type": "video",
            "timestamped": True,
            "segments": result.get(
                "segments",
                [],
            ),
            "chunks": chunks,
            "text": result.get(
                "text",
                "",
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "file_name": video_path.name,
            "media_type": "video",
            "error": str(exc),
        }