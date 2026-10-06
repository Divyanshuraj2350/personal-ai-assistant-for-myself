import os
import subprocess
from pathlib import Path


WHISPER_CLI = os.getenv(
    "WHISPER_CLI",
    os.path.expanduser(
        "~/whisper.cpp/build/bin/whisper-cli"
    ),
)

WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    os.path.expanduser(
        "~/whisper.cpp/models/ggml-large-v3-turbo.bin"
    ),
)

VAD_MODEL = os.getenv(
    "WHISPER_VAD_MODEL",
    os.path.expanduser(
        "~/whisper.cpp/models/ggml-silero-v6.2.0.bin"
    ),
)


class STTError(Exception):
    """Raised when local speech-to-text fails."""


def transcribe_audio(
    audio_path,
    language="auto",
    use_vad=True,
):
    """
    Transcribe an audio file using local whisper.cpp.

    Returns:
        {
            "text": "...",
            "language": language,
            "audio_path": "...",
        }
    """

    audio_path = Path(audio_path).expanduser().resolve()

    if not audio_path.exists():
        raise STTError(
            f"Audio file not found: {audio_path}"
        )

    if not Path(WHISPER_CLI).exists():
        raise STTError(
            f"whisper-cli not found: {WHISPER_CLI}"
        )

    if not Path(WHISPER_MODEL).exists():
        raise STTError(
            f"Whisper model not found: {WHISPER_MODEL}"
        )

    command = [
        WHISPER_CLI,
        "-m",
        WHISPER_MODEL,
        "-f",
        str(audio_path),
        "-l",
        language,
        "-nt",
        "-np",
    ]

    if use_vad:
        if not Path(VAD_MODEL).exists():
            raise STTError(
                f"VAD model not found: {VAD_MODEL}"
            )

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
        raise STTError(
            "Whisper transcription timed out."
        )
    except OSError as exc:
        raise STTError(
            f"Unable to start whisper-cli: {exc}"
        )

    if result.returncode != 0:
        error = result.stderr.strip()

        if not error:
            error = result.stdout.strip()

        raise STTError(
            f"Whisper failed: {error}"
        )

    text = result.stdout.strip()

    return {
        "text": text,
        "language": language,
        "audio_path": str(audio_path),
    }


def transcribe_file(audio_path):
    """
    Default local STT entry point.
    """

    return transcribe_audio(
        audio_path,
        language="auto",
        use_vad=True,
    )
