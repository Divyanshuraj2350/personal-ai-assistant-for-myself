import re


def _clean(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _normalize(value):
    value = _clean(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _get_personal(profile, key):
    personal = profile.get("personal", {})

    if not isinstance(personal, dict):
        return ""

    # Actual career_profile.json schema uses full_name.
    if key == "name":
        return _clean(personal.get("full_name"))

    return _clean(personal.get(key))


def _get_links(profile, key):
    links = profile.get("professional_links", {})

    if not isinstance(links, dict):
        return ""

    return _clean(links.get(key))


def _map_field(field, profile, tailored_resume=None):
    """
    Deterministically map an application field to trusted
    candidate information.

    No values are invented.
    """

    name = _normalize(field.get("name"))
    field_id = _normalize(field.get("id"))
    label = _normalize(field.get("label"))
    placeholder = _normalize(field.get("placeholder"))
    autocomplete = _normalize(field.get("autocomplete"))

    combined = " ".join(
        [
            name,
            field_id,
            label,
            placeholder,
            autocomplete,
        ]
    ).strip()

    field_type = _normalize(field.get("type"))

    # ---------------------------------------------------------
    # FULL NAME
    # ---------------------------------------------------------

    if (
        name in {"name", "full name", "fullname"}
        or field_id in {"name", "full name", "fullname"}
        or "full name" in label
    ):
        value = _get_personal(profile, "name")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.personal.name",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # EMAIL
    # ---------------------------------------------------------

    if (
        field_type == "email"
        or name in {"email", "email address"}
        or "email" in combined
    ):
        value = _get_personal(profile, "email")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.personal.email",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # PHONE
    # ---------------------------------------------------------

    if (
        name in {"phone", "mobile", "telephone", "phone number"}
        or "phone" in combined
        or "mobile" in combined
        or "telephone" in combined
    ):
        value = _get_personal(profile, "phone")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.personal.phone",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # LINKEDIN
    # ---------------------------------------------------------

    if "linkedin" in combined:
        value = _get_links(profile, "linkedin")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.links.linkedin",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # GITHUB
    # ---------------------------------------------------------

    if "github" in combined:
        value = _get_links(profile, "github")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.links.github",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # PORTFOLIO
    # ---------------------------------------------------------

    if (
        "portfolio" in combined
        or "personal website" in combined
    ):
        value = _get_links(profile, "portfolio")

        return {
            "field": field,
            "mapped": bool(value),
            "value": value or None,
            "source": "career_profile.links.portfolio",
            "confidence": "high" if value else "none",
            "action": "fill" if value else "leave_blank",
        }

    # ---------------------------------------------------------
    # CONSENT / OPTIONAL CONTACT
    # ---------------------------------------------------------

    if field_type == "checkbox":
        consent_words = [
            "keep my resume",
            "future job",
            "future opportunities",
            "contact me",
            "marketing",
            "newsletter",
            "privacy",
            "consent",
        ]

        if any(
            word in combined
            for word in consent_words
        ):
            return {
                "field": field,
                "mapped": False,
                "value": False,
                "source": "user_approval_required",
                "confidence": "high",
                "action": "leave_unchecked",
            }

    # ---------------------------------------------------------
    # RESUME / CV UPLOAD
    # ---------------------------------------------------------

    if (
        field_type == "file"
        or "resume" in combined
        or re.search(r"\bcv\b", combined)
    ):
        resume_path = None

        if isinstance(tailored_resume, dict):
            resume_path = tailored_resume.get(
                "file_path"
            )

        if resume_path:
            return {
                "field": field,
                "mapped": True,
                "value": resume_path,
                "source": "tailored_resume.file_path",
                "confidence": "high",
                "action": "upload",
            }

        return {
            "field": field,
            "mapped": False,
            "value": None,
            "source": "tailored_resume.file_path",
            "confidence": "none",
            "action": "requires_resume_file",
        }

    # ---------------------------------------------------------
    # UNKNOWN
    # ---------------------------------------------------------

    return {
        "field": field,
        "mapped": False,
        "value": None,
        "source": None,
        "confidence": "none",
        "action": "manual_review",
    }


def map_application_fields(
    application_result,
    profile,
    tailored_resume=None,
):
    """
    Map detected application fields to trusted sources.

    This function only prepares mappings.
    It does not interact with a browser.
    """

    if not isinstance(application_result, dict):
        return {
            "status": "error",
            "message": "Invalid application inspection result.",
            "mappings": [],
        }

    if application_result.get("status") != "success":
        return {
            "status": "error",
            "message": (
                application_result.get("message")
                or "Application inspection failed."
            ),
            "mappings": [],
        }

    fields = application_result.get("fields", [])

    mappings = [
        _map_field(
            field,
            profile,
            tailored_resume,
        )
        for field in fields
    ]

    mapped_count = sum(
        1
        for item in mappings
        if item.get("mapped")
    )

    manual_review_count = sum(
        1
        for item in mappings
        if item.get("action") == "manual_review"
    )

    approval_required_count = sum(
        1
        for item in mappings
        if item.get("source") == "user_approval_required"
    )

    return {
        "status": "success",
        "application_url": application_result.get(
            "application_url"
        ),
        "page_url": application_result.get(
            "final_url"
        ),
        "total_fields": len(fields),
        "mapped_fields": mapped_count,
        "manual_review_fields": manual_review_count,
        "approval_required_fields": (
            approval_required_count
        ),
        "mappings": mappings,
    }
