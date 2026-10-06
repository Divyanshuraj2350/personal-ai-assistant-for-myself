from pathlib import Path


def _clean(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _file_exists(path):
    if not path:
        return False

    try:
        return Path(path).is_file()
    except (TypeError, OSError):
        return False


def _build_proposed_field(mapping):
    field = mapping.get("field", {})

    return {
        "field_name": _clean(field.get("name")),
        "field_id": _clean(field.get("id")),
        "label": _clean(field.get("label")),
        "type": _clean(field.get("type")),
        "required": bool(field.get("required", False)),
        "value": mapping.get("value"),
        "source": mapping.get("source"),
        "confidence": mapping.get("confidence", "none"),
        "action": mapping.get("action", "manual_review"),
        "mapped": bool(mapping.get("mapped", False)),
    }


def prepare_application_proposal(
    application_result,
    mapping_result,
    tailored_resume_path=None,
):
    """
    Build a proposed application payload.

    This function does NOT:
    - open a browser
    - fill fields
    - upload files
    - submit an application

    It only prepares data for validation/review.
    """

    if not isinstance(application_result, dict):
        return {
            "status": "error",
            "message": "Invalid application inspection result.",
        }

    if application_result.get("status") != "success":
        return {
            "status": "error",
            "message": (
                application_result.get("message")
                or "Application inspection failed."
            ),
        }

    if not isinstance(mapping_result, dict):
        return {
            "status": "error",
            "message": "Invalid field mapping result.",
        }

    if mapping_result.get("status") != "success":
        return {
            "status": "error",
            "message": (
                mapping_result.get("message")
                or "Application field mapping failed."
            ),
        }

    mappings = mapping_result.get("mappings", [])

    proposed_fields = []

    for mapping in mappings:
        proposed = _build_proposed_field(mapping)

        # -----------------------------------------------------
        # Resume upload
        # -----------------------------------------------------

        if proposed["action"] == "requires_resume_file":

            if _file_exists(tailored_resume_path):
                proposed["value"] = str(
                    Path(tailored_resume_path).resolve()
                )
                proposed["source"] = (
                    "tailored_resume.file_path"
                )
                proposed["confidence"] = "high"
                proposed["action"] = "upload"
                proposed["mapped"] = True
            else:
                proposed["value"] = None
                proposed["action"] = (
                    "requires_resume_file"
                )

        proposed_fields.append(proposed)

    fill_fields = [
        item
        for item in proposed_fields
        if item["action"] == "fill"
        and item["mapped"]
    ]

    upload_fields = [
        item
        for item in proposed_fields
        if item["action"] == "upload"
        and item["mapped"]
    ]

    leave_blank_fields = [
        item
        for item in proposed_fields
        if item["action"] == "leave_blank"
    ]

    manual_review_fields = [
        item
        for item in proposed_fields
        if item["action"] == "manual_review"
    ]

    approval_fields = [
        item
        for item in proposed_fields
        if item["source"] == "user_approval_required"
    ]

    unresolved_required_fields = [
        item
        for item in proposed_fields
        if item["required"]
        and item["action"] in {
            "manual_review",
            "requires_resume_file",
        }
    ]

    return {
        "status": "success",
        "application_url": (
            application_result.get("application_url")
            or application_result.get("final_url")
        ),
        "page_url": application_result.get(
            "final_url"
        ),
        "proposal_ready": (
            len(unresolved_required_fields) == 0
        ),
        "total_fields": len(proposed_fields),
        "fill_field_count": len(fill_fields),
        "upload_field_count": len(upload_fields),
        "leave_blank_count": len(
            leave_blank_fields
        ),
        "manual_review_count": len(
            manual_review_fields
        ),
        "approval_required_count": len(
            approval_fields
        ),
        "unresolved_required_count": len(
            unresolved_required_fields
        ),
        "fields": proposed_fields,
        "unresolved_required_fields": (
            unresolved_required_fields
        ),
    }
