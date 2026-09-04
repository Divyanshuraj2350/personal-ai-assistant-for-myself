from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance
import pytesseract

from app.rag.store import add_document


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def preprocess_image(image):
    # Convert to RGB
    image = image.convert("RGB")

    # Make the image larger for OCR
    width, height = image.size

    if width < 1600:
        scale = 1600 / width
        image = image.resize(
            (int(width * scale), int(height * scale))
        )

    # Convert to grayscale
    image = ImageOps.grayscale(image)

    # Improve contrast
    image = ImageEnhance.Contrast(image).enhance(2.0)

    return image


def extract_text_from_image(image_path):
    image_path = Path(image_path)

    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format: {image_path.suffix}"
        )

    image = Image.open(image_path)

    # First attempt: original image
    text = pytesseract.image_to_string(
        image,
        config="--psm 6",
    ).strip()

    if text:
        return text

    # Second attempt: processed image
    processed_image = preprocess_image(image)

    text = pytesseract.image_to_string(
        processed_image,
        config="--psm 6",
    ).strip()

    if text:
        return text

    # Final fallback for sparse text
    text = pytesseract.image_to_string(
        processed_image,
        config="--psm 11",
    ).strip()

    return text


def ingest_image(image_path):
    image_path = Path(image_path)

    text = extract_text_from_image(image_path)

    if not text:
        return {
            "status": "empty",
            "file": image_path.name,
            "message": "No text could be extracted from the image.",
        }

    document_id = f"image_{image_path.stem}"

    add_document(
        document_id=document_id,
        text=text,
    )

    return {
        "status": "success",
        "file": image_path.name,
        "characters": len(text),
        "text": text,
    }