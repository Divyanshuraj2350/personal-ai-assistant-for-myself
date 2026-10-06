from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance
import pytesseract

from app.rag.ingest import ingest_text


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
}


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess_image(image):
    """
    Prepare an image for OCR.
    """

    image = image.convert("RGB")

    width, height = image.size

    # Enlarge small images for better OCR.
    if width < 1600:
        scale = 1600 / width

        image = image.resize(
            (
                int(width * scale),
                int(height * scale),
            )
        )

    # Convert to grayscale.
    image = ImageOps.grayscale(image)

    # Improve contrast.
    image = ImageEnhance.Contrast(
        image
    ).enhance(2.0)

    return image


# ============================================================
# OCR
# ============================================================

def extract_text_from_image(image_path):
    """
    Extract text from an image using Tesseract OCR.
    """

    path = Path(image_path)

    if not path.exists():
        return {
            "status": "error",
            "error": "Image file does not exist.",
        }

    if not path.is_file():
        return {
            "status": "error",
            "error": "Path is not a file.",
        }

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {
            "status": "error",
            "error": (
                f"Unsupported image format: "
                f"{path.suffix.lower()}"
            ),
        }

    try:
        image = Image.open(path)

        # ----------------------------------------------------
        # Attempt 1: Original image
        # ----------------------------------------------------

        text = pytesseract.image_to_string(
            image,
            config="--psm 6",
        ).strip()

        if text:
            return {
                "status": "success",
                "text": text,
            }

        # ----------------------------------------------------
        # Attempt 2: Preprocessed image
        # ----------------------------------------------------

        processed_image = preprocess_image(
            image
        )

        text = pytesseract.image_to_string(
            processed_image,
            config="--psm 6",
        ).strip()

        if text:
            return {
                "status": "success",
                "text": text,
            }

        # ----------------------------------------------------
        # Attempt 3: Sparse text
        # ----------------------------------------------------

        text = pytesseract.image_to_string(
            processed_image,
            config="--psm 11",
        ).strip()

        if text:
            return {
                "status": "success",
                "text": text,
            }

        return {
            "status": "empty",
            "error": (
                "No text could be extracted "
                "from the image."
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }


# ============================================================
# IMAGE → RAG
# ============================================================

def ingest_image(image_path):
    """
    Extract OCR text from an image and send it
    through the existing RAG ingestion pipeline.
    """

    path = Path(image_path)

    extraction = extract_text_from_image(
        image_path
    )

    if extraction.get("status") != "success":
        return {
            **extraction,
            "file": path.name,
        }

    text = extraction["text"]

    metadata = {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_path": str(path),
        "media_type": "image",
        "processing_method": "ocr",
    }

    result = ingest_text(
        text=text,
        source="image",
        metadata=metadata,
    )

    return {
        **result,
        "file": path.name,
        "characters": len(text),
        "text": text,
    }