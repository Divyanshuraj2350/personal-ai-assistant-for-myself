import json
import re

import httpx

from app.media.file_registry import get_file_record
from app.media.document_processor import _ocr_pdf
from app.rag.store import get_document_chunks


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


class ResumeExtractionError(Exception):
    """Raised when resume information cannot be extracted."""
    pass


def _empty_resume():
    return {
        "personal": {
            "full_name": None,
            "email": None,
            "phone": None,
            "location": None,
        },
        "professional_links": {
            "linkedin": None,
            "github": None,
            "portfolio": None,
        },
        "education": [],
        "experience": [],
        "projects": [],
        "skills": {
            "programming_languages": [],
            "ai_machine_learning": [],
            "web_backend": [],
            "systems_linux": [],
            "databases": [],
            "tools_platforms": [],
            "blockchain": [],
        },
        "certifications": [],
        "achievements": [],
    }


def _normalize_string(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return str(value).strip() or None


def _normalize_list(value):
    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        if item is None:
            continue

        if isinstance(item, str):
            cleaned = item.strip()

        elif isinstance(item, dict):
            cleaned = item

        else:
            cleaned = str(item).strip()

        if cleaned:
            result.append(cleaned)

    return result


def _normalize_resume(data):
    """
    Normalize Qwen output into a predictable schema.

    Missing information remains None or [].
    No information is invented here.
    """

    result = _empty_resume()

    if not isinstance(data, dict):
        return result

    personal = data.get("personal")

    if isinstance(personal, dict):
        for field in result["personal"]:
            result["personal"][field] = _normalize_string(
                personal.get(field)
            )

    links = data.get("professional_links")

    if isinstance(links, dict):
        for field in result["professional_links"]:
            result["professional_links"][field] = _normalize_string(
                links.get(field)
            )

    for field in [
        "education",
        "experience",
        "projects",
        "certifications",
        "achievements",
    ]:
        result[field] = _normalize_list(
            data.get(field)
        )

    skills = data.get("skills")

    if isinstance(skills, dict):
        for field in result["skills"]:
            result["skills"][field] = _normalize_list(
                skills.get(field)
            )

    return result


SUSPICIOUS_TEXT_PATTERN = re.compile(r"[A-Za-z]\d+[A-Za-z]")

def _find_suspicious_text(
    text,
    source,
    limit=20,
):
    """
    Flag likely PDF/OCR character corruption for human review.

    This function never changes source text or attempts to guess
    intended wording. It only reports suspicious fragments.

    Known legitimate alphanumeric tokens such as AI4I are ignored
    because the corruption pattern can otherwise match a substring
    inside them.
    """

    if not isinstance(text, str):
        return []

    findings = []

    # Legitimate tokens that can contain a pattern such as I4I.
    # These are not OCR corruption.
    legitimate_tokens = {
        "AI4I",
    }

    for match in SUSPICIOUS_TEXT_PATTERN.finditer(text):
        # Expand the match to the surrounding alphanumeric token.
        # Example:
        #     AI4I
        #      ^^^
        # The regex sees "I4I", but the complete token is "AI4I".
        token_start = match.start()

        while (
            token_start > 0
            and text[token_start - 1].isalnum()
        ):
            token_start -= 1

        token_end = match.end()

        while (
            token_end < len(text)
            and text[token_end].isalnum()
        ):
            token_end += 1

        full_token = text[token_start:token_end].strip()

        if full_token.upper() in legitimate_tokens:
            continue

        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)

        findings.append(
            {
                "source": source,
                "fragment": text[start:end].strip(),
                "match": match.group(0),
            }
        )

        if len(findings) >= limit:
            break

    return findings


def _build_quality_report(
    resume_text,
    resume,
    source_method,
):
    """
    Report extraction-quality risks without rewriting any content.

    A resume with suspicious source artifacts requires human review
    before it can be used for application-field mapping.
    """

    source_findings = _find_suspicious_text(
        resume_text,
        source=source_method,
    )

    extracted_findings = []

    for section, value in resume.items():
        if isinstance(value, str):
            extracted_findings.extend(
                _find_suspicious_text(
                    value,
                    source=f"resume.{section}",
                )
            )

        elif isinstance(value, dict):
            for field, field_value in value.items():
                extracted_findings.extend(
                    _find_suspicious_text(
                        field_value,
                        source=f"resume.{section}.{field}",
                    )
                )

        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    extracted_findings.extend(
                        _find_suspicious_text(
                            item,
                            source=f"resume.{section}[{index}]",
                        )
                    )

    findings = source_findings + extracted_findings

    if findings:
        return {
            "status": "review_required",
            "can_use_for_application_mapping": False,
            "message": (
                "Possible PDF/OCR character corruption was found. "
                "Review the original uploaded resume before using "
                "this extraction for an application."
            ),
            "findings": findings[:20],
        }

    return {
        "status": "passed",
        "can_use_for_application_mapping": True,
        "message": (
            "No likely PDF/OCR character-corruption patterns "
            "were found."
        ),
        "findings": [],
    }


def _select_resume_source_text(
    record,
    document_text,
):
    """
    Prefer the existing RAG document text. If it has likely
    character corruption, compare it with the existing OCR
    fallback and use OCR only when it has fewer such artifacts.

    No extracted text is rewritten or merged.
    """

    source_method = "rag_document_text"

    document_findings = _find_suspicious_text(
        document_text,
        source=source_method,
    )

    if not document_findings:
        return document_text, source_method

    file_path = record.get("file_path")

    if not file_path:
        return document_text, source_method

    ocr_result = _ocr_pdf(file_path)

    if ocr_result.get("status") != "success":
        return document_text, source_method

    ocr_text = str(
        ocr_result.get("text", "")
    ).strip()

    if not ocr_text:
        return document_text, source_method

    ocr_findings = _find_suspicious_text(
        ocr_text,
        source="pdf_ocr_fallback",
    )

    if len(ocr_findings) < len(document_findings):
        return ocr_text, "pdf_ocr_fallback"

    return document_text, source_method


def _extract_json(text):
    """
    Extract JSON from Qwen's response.

    Handles plain JSON and fenced JSON.
    """

    if not isinstance(text, str):
        return None

    text = text.strip()

    if not text:
        return None

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return None

        try:
            return json.loads(
                text[start:end + 1]
            )
        except json.JSONDecodeError:
            return None


async def _call_qwen(resume_text):
    prompt = f"""
Extract structured information from the resume below.

IMPORTANT RULES:

1. Use ONLY information explicitly present in the resume.
2. Do NOT invent missing information.
3. Do NOT use outside knowledge.
4. Do NOT use any stored candidate profile.
5. Do NOT improve, rewrite, tailor, or summarize the resume.
6. Preserve factual information from the resume.
7. If a field is not present, return null for scalar fields
   or [] for list fields.
8. Separate projects from employment experience.
9. Preserve technologies and skills under the appropriate
   skill category.
10. Do not infer work authorization, visa status, sponsorship,
    citizenship, or other legal/personal eligibility information
    unless explicitly stated in the resume.
11. Return ONLY valid JSON.
12. Do not include markdown fences.
13. The extracted PDF text may contain character corruption.
    Do not guess a correction from outside knowledge. Preserve
    uncertain text exactly as received.

Return exactly this structure:

{{
  "personal": {{
    "full_name": null,
    "email": null,
    "phone": null,
    "location": null
  }},
  "professional_links": {{
    "linkedin": null,
    "github": null,
    "portfolio": null
  }},
  "education": [],
  "experience": [],
  "projects": [],
  "skills": {{
    "programming_languages": [],
    "ai_machine_learning": [],
    "web_backend": [],
    "systems_linux": [],
    "databases": [],
    "tools_platforms": [],
    "blockchain": []
  }},
  "certifications": [],
  "achievements": []
}}

RESUME:

{resume_text}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract structured resume information. "
                    "Never invent information."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,
                write=30.0,
                pool=30.0,
            )
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

    except Exception as exc:
        raise ResumeExtractionError(
            f"Could not contact Qwen: {exc}"
        ) from exc

    message = data.get("message", {})

    if not isinstance(message, dict):
        raise ResumeExtractionError(
            "Qwen returned an invalid response."
        )

    content = message.get("content", "")

    parsed = _extract_json(content)

    if parsed is None:
        raise ResumeExtractionError(
            "Qwen did not return valid JSON."
        )

    return parsed


async def extract_resume(file_id):
    """
    Extract structured information from a previously uploaded
    Career Assistant resume.

    The original PDF is never modified.
    """

    if not file_id:
        raise ResumeExtractionError(
            "A resume file ID is required."
        )

    # ---------------------------------------------------------
    # Resolve registered file
    # ---------------------------------------------------------

    record = get_file_record(file_id)

    if record is None:
        raise ResumeExtractionError(
            "Resume file was not found in the file registry."
        )

    if record.get("file_extension") != ".pdf":
        raise ResumeExtractionError(
            "Career Assistant resume extraction requires a PDF."
        )

    if record.get("media_type") != "document":
        raise ResumeExtractionError(
            "Registered resume is not a document."
        )

    if record.get("processing_status") != "completed":
        raise ResumeExtractionError(
            "Resume processing has not completed."
        )

    document_id = record.get(
        "rag_document_id"
    )

    if not document_id:
        raise ResumeExtractionError(
            "Resume has no associated RAG document."
        )

    # ---------------------------------------------------------
    # Retrieve every chunk for this exact resume
    # ---------------------------------------------------------

    chunks = get_document_chunks(
        document_id
    )

    if not chunks:
        raise ResumeExtractionError(
            "No extracted resume content was found."
        )

    chunks = sorted(
        chunks,
        key=lambda item: item.get(
            "metadata",
            {}
        ).get(
            "chunk_index",
            0,
        ),
    )

    resume_text = "\n\n".join(
        chunk["content"]
        for chunk in chunks
        if chunk.get("content")
    ).strip()

    if not resume_text:
        raise ResumeExtractionError(
            "The extracted resume text is empty."
        )

    resume_text, source_method = _select_resume_source_text(
        record,
        resume_text,
    )

    # ---------------------------------------------------------
    # Structured extraction
    # ---------------------------------------------------------

    extracted = await _call_qwen(
        resume_text
    )

    normalized = _normalize_resume(
        extracted
    )

    quality = _build_quality_report(
        resume_text,
        normalized,
        source_method,
    )

    # ---------------------------------------------------------
    # Return source information alongside extraction
    # ---------------------------------------------------------

    return {
        "status": "success",
        "file_id": file_id,
        "file_name": record.get("file_name"),
        "rag_document_id": document_id,
        "chunk_count": len(chunks),
        "resume_source": "user_uploaded_original",
        "extraction_source": source_method,
        "resume": normalized,
        "quality": quality,
    }
