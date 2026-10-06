import re
from pathlib import Path
from urllib.parse import urlparse


EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{7,20}$")

ALLOWED_URL_SCHEMES = {"http", "https"}


def _is_valid_email(value):
    if not isinstance(value, str):
        return False
    return bool(EMAIL_RE.match(value.strip()))


def _is_valid_phone(value):
    if not isinstance(value, str):
        return False

    cleaned = value.strip()

    if not PHONE_RE.match(cleaned):
        return False

    digits = re.sub(r"\D", "", cleaned)
    return 8 <= len(digits) <= 15


def _is_valid_url(value):
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        parsed = urlparse(value.strip())
        return (
            parsed.scheme.lower() in ALLOWED_URL_SCHEMES
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def _validate_field(field):
    errors = []
    warnings = []

    label = field.get("label", "")
    field_type = field.get("type", "")
    value = field.get("value")
    required = bool(field.get("required"))
    action = field.get("action")
    source = field.get("source")

    # Required unresolved fields
    if required:
        if action in {
            "manual_review",
            "requires_resume_file",
        }:
            errors.append(
                f"Required field requires resolution: {label}"
            )

        if source == "user_approval_required":
            errors.append(
                f"User approval required: {label}"
            )

        if action == "fill" and (
            value is None or str(value).strip() == ""
        ):
            errors.append(
                f"Required field has no value: {label}"
            )

    # Email
    if field_type == "email" and action == "fill":
        if not _is_valid_email(value):
            errors.append(
                f"Invalid email value: {label}"
            )

    # Phone
    if (
        field_type in {"tel", "phone", "text"}
        and "phone" in label.lower()
        and action == "fill"
    ):
        if not _is_valid_phone(value):
            errors.append(
                f"Invalid phone value: {label}"
            )

    # URLs
    if action == "fill" and (
        "url" in field_type.lower()
        or "linkedin" in label.lower()
        or "github" in label.lower()
        or "website" in label.lower()
    ):
        if not _is_valid_url(value):
            errors.append(
                f"Invalid URL value: {label}"
            )

    # Consent
    if field_type == "checkbox":
        if source == "user_approval_required":
            warnings.append(
                f"Consent decision required from user: {label}"
            )

        if value is True and source == "user_approval_required":
            errors.append(
                f"Consent cannot be enabled without explicit approval: {label}"
            )

    # Manual review
    if action == "manual_review":
        warnings.append(
            f"Manual review required: {label}"
        )

    # Resume
    if action == "requires_resume_file":
        resume_path = value

        if resume_path:
            if not Path(resume_path).is_file():
                errors.append(
                    f"Resume file does not exist: {resume_path}"
                )
        else:
            warnings.append(
                "Resume file has not been supplied yet."
            )

    return errors, warnings


def validate_application_proposal(proposal):
    """
    Validate a prepared application proposal.

    This function performs validation only.
    It does not open a browser, fill fields, upload files,
    check consent boxes, or submit an application.
    """

    if not isinstance(proposal, dict):
        return {
            "status": "error",
            "valid": False,
            "safe_to_fill": False,
            "errors": ["Invalid proposal object."],
            "warnings": [],
            "field_results": [],
        }

    if proposal.get("status") != "success":
        return {
            "status": "error",
            "valid": False,
            "safe_to_fill": False,
            "errors": ["Application proposal was not successful."],
            "warnings": [],
            "field_results": [],
        }

    fields = proposal.get("fields", [])

    errors = []
    warnings = []
    field_results = []

    for field in fields:
        field_errors, field_warnings = _validate_field(field)

        field_results.append(
            {
                "field_name": field.get("field_name"),
                "label": field.get("label"),
                "valid": not bool(field_errors),
                "errors": field_errors,
                "warnings": field_warnings,
            }
        )

        errors.extend(field_errors)
        warnings.extend(field_warnings)

    # Preserve proposal-level unresolved required fields
    unresolved = proposal.get("unresolved_required_fields", [])

    if unresolved:
        for field in unresolved:
            message = (
                f"Unresolved required field: "
                f"{field.get('label', field.get('field_name', 'unknown'))}"
            )

            if message not in errors:
                errors.append(message)

    valid = len(errors) == 0

    return {
        "status": "success",
        "valid": valid,
        "safe_to_fill": valid,
        "safe_to_submit": False,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "field_count": len(fields),
        "field_results": field_results,
        "submission_approval_required": True,
    }
