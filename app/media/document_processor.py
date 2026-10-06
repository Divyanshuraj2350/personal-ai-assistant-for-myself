from pathlib import Path
import subprocess
import tempfile

from pypdf import PdfReader
from docx import Document

from app.rag.ingest import ingest_text
from app.rag.image_ingest import extract_text_from_image


SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
}

PDF_RENDER_DPI = 150

PDFTOPPM_COMMAND = "pdftoppm"


# ============================================================
# TXT
# ============================================================

def extract_txt(file_path):
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

    try:
        text = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return {
            "status": "error",
            "error": "The TXT file is not UTF-8 encoded.",
        }
    except OSError as error:
        return {
            "status": "error",
            "error": str(error),
        }

    if not text.strip():
        return {
            "status": "error",
            "error": "The TXT file is empty.",
        }

    return {
        "status": "success",
        "text": text,
        "processing_method": "text",
    }


# ============================================================
# PDF — NORMAL TEXT EXTRACTION
# ============================================================

def _extract_pdf_text(file_path):
    """
    Try extracting normal embedded PDF text using pypdf.
    """

    path = Path(file_path)

    try:
        reader = PdfReader(str(path))

        pages = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text and page_text.strip():
                pages.append(page_text)

        text = "\n\n".join(pages)

    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }

    if not text.strip():
        return {
            "status": "error",
            "error": "No extractable text was found in the PDF.",
        }

    return {
        "status": "success",
        "text": text,
        "processing_method": "pdf_text",
    }


# ============================================================
# PDF — OCR FALLBACK
# ============================================================

def _ocr_pdf(file_path):
    """
    Render an image-only/scanned PDF into PNG pages
    and process each page using the existing image OCR pipeline.
    """

    path = Path(file_path)

    try:
        with tempfile.TemporaryDirectory(
            prefix="pdf_ocr_"
        ) as temp_dir:

            output_prefix = Path(temp_dir) / "page"

            command = [
                PDFTOPPM_COMMAND,
                "-png",
                "-r",
                str(PDF_RENDER_DPI),
                str(path),
                str(output_prefix),
            ]

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

            if completed.returncode != 0:
                error_message = (
                    completed.stderr.strip()
                    or "PDF rendering failed."
                )

                return {
                    "status": "error",
                    "error": error_message,
                }

            image_pages = sorted(
                Path(temp_dir).glob("page-*.png")
            )

            if not image_pages:
                return {
                    "status": "error",
                    "error": (
                        "PDF rendering produced no image pages."
                    ),
                }

            pages = []

            for image_path in image_pages:

                ocr_result = extract_text_from_image(
                    image_path
                )

                if ocr_result.get("status") != "success":
                    continue

                page_text = ocr_result.get(
                    "text",
                    ""
                )

                if page_text and page_text.strip():
                    pages.append(
                        page_text.strip()
                    )

            text = "\n\n".join(pages)

            if not text.strip():
                return {
                    "status": "error",
                    "error": (
                        "No readable text was found "
                        "in the PDF using OCR."
                    ),
                }

            return {
                "status": "success",
                "text": text,
                "processing_method": "pdf_ocr",
            }

    except FileNotFoundError:
        return {
            "status": "error",
            "error": (
                "pdftoppm was not found. "
                "Install Poppler with: brew install poppler"
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }


# ============================================================
# PDF
# ============================================================

def extract_pdf(file_path):
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

    # --------------------------------------------------------
    # First attempt: normal PDF text extraction
    # --------------------------------------------------------

    text_result = _extract_pdf_text(
        file_path
    )

    if text_result.get("status") == "success":
        return text_result

    # --------------------------------------------------------
    # Fallback: scanned/image-only PDF OCR
    # --------------------------------------------------------

    return _ocr_pdf(
        file_path
    )


# ============================================================
# DOCX
# ============================================================

def extract_docx(file_path):
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

    try:
        document = Document(str(path))

        paragraphs = []

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                paragraphs.append(text)

        text = "\n\n".join(paragraphs)

    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }

    if not text.strip():
        return {
            "status": "error",
            "error": (
                "No extractable text was found in the DOCX file."
            ),
        }

    return {
        "status": "success",
        "text": text,
        "processing_method": "docx_text",
    }


# ============================================================
# UNIFIED DOCUMENT EXTRACTION
# ============================================================

def extract_document(file_path):
    """
    Detect and extract text from a supported document.
    """

    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return {
            "status": "error",
            "error": f"Unsupported document type: {extension}",
        }

    if extension == ".txt":
        return extract_txt(
            file_path
        )

    if extension == ".pdf":
        return extract_pdf(
            file_path
        )

    if extension == ".docx":
        return extract_docx(
            file_path
        )

    return {
        "status": "error",
        "error": "Could not determine document type.",
    }


# ============================================================
# DOCUMENT → RAG
# ============================================================

def ingest_document(file_path):
    """
    Extract a document and send its text through
    the existing RAG ingestion pipeline.
    """

    path = Path(file_path)

    extraction = extract_document(
        file_path
    )

    if extraction.get("status") != "success":
        return extraction

    metadata = {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_path": str(path),
        "media_type": "document",
        "processing_method": extraction.get(
            "processing_method"
        ),
    }

    result = ingest_text(
        text=extraction["text"],
        source="document",
        metadata=metadata,
    )

    # Preserve extraction information.
    if isinstance(result, dict):
        result["processing_method"] = extraction.get(
            "processing_method"
        )

    return result