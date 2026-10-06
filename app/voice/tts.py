import os
import uuid
from pathlib import Path

from mlx_audio.tts.generate import generate_audio


TTS_MODEL = os.getenv(
    "TTS_MODEL",
    "mlx-community/chatterbox-multilingual-v3",
)

TTS_REFERENCE_AUDIO = os.getenv(
    "TTS_REFERENCE_AUDIO",
    os.path.expanduser(
        "~/Desktop/tts_reference_clean.wav"
    ),
)

TTS_OUTPUT_DIR = os.getenv(
    "TTS_OUTPUT_DIR",
    os.path.expanduser(
        "~/My ai/data/voice"
    ),
)


class TTSError(Exception):
    """Raised when local text-to-speech fails."""


def synthesize_speech(
    text,
    language="en",
    reference_audio=None,
    output_dir=None,
):
    """
    Generate speech locally using Chatterbox Multilingual v3.

    Returns:
        {
            "audio_path": "...",
            "text": "...",
            "language": "...",
        }
    """

    text = str(text).strip()

    if not text:
        raise TTSError("Text for speech generation is empty.")

    reference_audio = Path(
        reference_audio or TTS_REFERENCE_AUDIO
    ).expanduser().resolve()

    if not reference_audio.exists():
        raise TTSError(
            f"Reference audio not found: {reference_audio}"
        )

    output_dir = Path(
        output_dir or TTS_OUTPUT_DIR
    ).expanduser().resolve()

    try:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise TTSError(
            f"Unable to create TTS output directory: {exc}"
        )

    file_prefix = f"tts_{uuid.uuid4().hex}"

    try:
        generate_audio(
            text=text,
            model=TTS_MODEL,
            lang_code=language,
            ref_audio=str(reference_audio),
            output_path=str(output_dir),
            file_prefix=file_prefix,
            audio_format="wav",
            verbose=False,
        )
    except Exception as exc:
        raise TTSError(
            f"Chatterbox TTS generation failed: {exc}"
        ) from exc

    wav_files = sorted(
        output_dir.glob(f"{file_prefix}*.wav"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not wav_files:
        raise TTSError(
            "TTS generation completed but no WAV file was found."
        )

    return {
        "audio_path": str(wav_files[0]),
        "text": text,
        "language": language,
    }


def synthesize_file(text, language="en"):
    """
    Default local TTS entry point.
    """

    return synthesize_speech(
        text,
        language=language,
    )