import re


def _clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def _normalize(value):
    value = _clean(value).lower()

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    ).strip()


def _get_nested(data, *keys):
    """
    Safely retrieve a nested value from the
    CA-4 extracted resume structure.
    """

    current = data

    for key in keys:
        if not isinstance(current, dict):
            return ""

        current = current.get(key)

    return _clean(current)


def _build_mapping(
    field,
    value=None,
    source=None,
    confidence="none",
    action="manual_review",
    mapped=False,
    requires_user=False,
):
    """
    Build one deterministic application-field mapping.

    No value is invented.
    """

    return {
        "field": field,
        "mapped": bool(mapped),
        "value": value if value else None,
        "source": source,
        "confidence": confidence,
        "action": action,
        "requires_user": bool(requires_user),
    }


def _map_field(
    field,
    resume,
    original_resume_file_path=None,
):
    """
    Map one detected application field to the
    structured resume extracted in CA-4.

    This function is deterministic.

    It does NOT:
        - use Qwen
        - invent values
        - infer legal information
        - infer human decisions
        - interact with the browser
        - submit anything
    """

    if not isinstance(field, dict):
        return _build_mapping(
            field={},
            action="manual_review",
            requires_user=True,
        )

    if not isinstance(resume, dict):
        resume = {}

    name = _normalize(field.get("name"))
    field_id = _normalize(field.get("id"))
    label = _normalize(field.get("label"))
    placeholder = _normalize(
        field.get("placeholder")
    )
    autocomplete = _normalize(
        field.get("autocomplete")
    )

    combined = " ".join(
        [
            name,
            field_id,
            label,
            placeholder,
            autocomplete,
        ]
    ).strip()

    field_type = _normalize(
        field.get("type")
    )
    # ---------------------------------------------------------
    # RESUME / CV FILE
    # ---------------------------------------------------------

    if (
        field_type == "file"
        or "resume" in combined
        or re.search(
            r"\bcv\b",
            combined,
        )
    ):
        if original_resume_file_path:
            return _build_mapping(
                field=field,
                value=original_resume_file_path,
                source="original_resume.file_path",
                confidence="high",
                action="upload",
                mapped=True,
                requires_user=False,
            )

        return _build_mapping(
            field=field,
            value=None,
            source="original_resume.file_path",
            confidence="none",
            action="requires_resume_file",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # FIRST NAME
    # ---------------------------------------------------------

    if (
        name in {
            "first name",
            "firstname",
            "given name",
        }
        or field_id in {
            "first name",
            "firstname",
            "given name",
        }
        or (
            "first name" in label
            and "preferred" not in label
        )
    ):
        full_name = _get_nested(
            resume,
            "personal",
            "full_name",
        )

        parts = full_name.split()

        value = parts[0] if parts else ""

        return _build_mapping(
            field=field,
            value=value,
            source="resume.personal.full_name",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # LAST NAME
    # ---------------------------------------------------------

    if (
        name in {
            "last name",
            "lastname",
            "family name",
            "surname",
        }
        or field_id in {
            "last name",
            "lastname",
            "family name",
            "surname",
        }
        or "last name" in label
    ):
        full_name = _get_nested(
            resume,
            "personal",
            "full_name",
        )

        parts = full_name.split()

        value = (
            " ".join(parts[1:])
            if len(parts) > 1
            else ""
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.personal.full_name",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # FULL NAME
    # ---------------------------------------------------------

    if (
        name in {
            "name",
            "full name",
            "fullname",
        }
        or field_id in {
            "name",
            "full name",
            "fullname",
        }
        or "full name" in label
    ):
        value = _get_nested(
            resume,
            "personal",
            "full_name",
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.personal.full_name",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # PREFERRED NAME
    # ---------------------------------------------------------

    if (
        "preferred name" in combined
        or "preferred_name" in combined
    ):
        return _build_mapping(
            field=field,
            action="manual_review",
            source=None,
            confidence="none",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # EMAIL
    # ---------------------------------------------------------

    if (
        field_type == "email"
        or name in {
            "email",
            "email address",
        }
        or "email" in combined
    ):
        value = _get_nested(
            resume,
            "personal",
            "email",
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.personal.email",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # PHONE
    # ---------------------------------------------------------

    if (
            field_type != "file"
            and (
            name in {
                "phone",
                "mobile",
                "telephone",
                "phone number",
                "mobile number",
            }
            or "phone" in combined
            or "mobile" in combined
            or "telephone" in combined
        )
    ):
        value = _get_nested(
            resume,
            "personal",
            "phone",
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.personal.phone",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # LOCATION / CITY
    # ---------------------------------------------------------

    if (
        name == "city"
        or field_id == "city"
        or "city" in combined
    ):
        location = _get_nested(
            resume,
            "personal",
            "location",
        )

        city = location.split(",")[0].strip()

        return _build_mapping(
            field=field,
            value=city,
            source="resume.personal.location",
            confidence="medium" if city else "none",
            action="fill" if city else "manual_review",
            mapped=bool(city),
            requires_user=not bool(city),
        )

    # ---------------------------------------------------------
    # COUNTRY
    # ---------------------------------------------------------

    if (
        name == "country"
        or field_id == "country"
        or "country" in combined
    ):
        location = _get_nested(
            resume,
            "personal",
            "location",
        )

        parts = [
            part.strip()
            for part in location.split(",")
            if part.strip()
        ]

        country = (
            parts[-1]
            if len(parts) > 1
            else ""
        )

        # Do NOT infer country from nationality.
        # This only uses the explicit location text
        # present in the extracted resume.
        return _build_mapping(
            field=field,
            value=country,
            source="resume.personal.location",
            confidence="medium" if country else "none",
            action="fill" if country else "manual_review",
            mapped=bool(country),
            requires_user=not bool(country),
        )

    # ---------------------------------------------------------
    # LINKEDIN
    # ---------------------------------------------------------

    if "linkedin" in combined:
        value = _get_nested(
            resume,
            "professional_links",
            "linkedin",
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.professional_links.linkedin",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # GITHUB
    # ---------------------------------------------------------

    if "github" in combined:
        value = _get_nested(
            resume,
            "professional_links",
            "github",
        )

        return _build_mapping(
            field=field,
            value=value,
            source="resume.professional_links.github",
            confidence="high" if value else "none",
            action="fill" if value else "manual_review",
            mapped=bool(value),
            requires_user=not bool(value),
        )

    # ---------------------------------------------------------
    # PORTFOLIO / WEBSITE
    # ---------------------------------------------------------

    if (
        "portfolio" in combined
        or "personal website" in combined
        or "website" in combined
    ):
        value = _get_nested(
            resume,
            "professional_links",
            "portfolio",
        )

        if value:
            return _build_mapping(
                field=field,
                value=value,
                source="resume.professional_links.portfolio",
                confidence="high",
                action="fill",
                mapped=True,
                requires_user=False,
            )

        return _build_mapping(
            field=field,
            action="manual_review",
            source=None,
            confidence="none",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # LEGAL / WORK AUTHORIZATION
    # ---------------------------------------------------------

    legal_signals = [
        "work authorization",
        "authorized to work",
        "legally authorized",
        "right to work",
        "employment authorization",
        "eligible to work",
        "work eligibility",
        "visa",
        "immigration",
        "citizenship",
    ]

    if any(
        signal in combined
        for signal in legal_signals
    ):
        return _build_mapping(
            field=field,
            value=None,
            source=None,
            confidence="none",
            action="manual_review",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # SPONSORSHIP
    # ---------------------------------------------------------

    sponsorship_signals = [
        "sponsorship",
        "sponsor",
        "require sponsorship",
        "visa sponsorship",
        "future sponsorship",
    ]

    if any(
        signal in combined
        for signal in sponsorship_signals
    ):
        return _build_mapping(
            field=field,
            value=None,
            source=None,
            confidence="none",
            action="manual_review",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # EDUCATION / DEGREE
    # ---------------------------------------------------------

    if (
        "degree" in combined
        or "education" in combined
        or "university" in combined
        or "college" in combined
        or "school" in combined
    ):
        education = resume.get(
            "education",
            [],
        )

        if isinstance(education, list) and education:
            first_education = education[0]

            if isinstance(
                first_education,
                dict,
            ):
                value = _clean(
                    first_education.get(
                        "degree"
                    )
                )

                if value:
                    return _build_mapping(
                        field=field,
                        value=value,
                        source=(
                            "resume.education[0].degree"
                        ),
                        confidence="high",
                        action="fill",
                        mapped=True,
                        requires_user=False,
                    )

        return _build_mapping(
            field=field,
            action="manual_review",
            mapped=False,
            requires_user=True,
        )

    # ---------------------------------------------------------
    # EXPERIENCE-BASED QUESTIONS
    # ---------------------------------------------------------

    experience_signals = [
        "experience",
        "years of experience",
        "professional experience",
        "machine learning experience",
        "ml experience",
        "predictive model",
        "predictive modeling",
    ]

    if any(
        signal in combined
        for signal in experience_signals
    ):
        return _build_mapping(
            field=field,
            value=None,
            source=None,
            confidence="none",
            action="manual_review",
            mapped=False,
            requires_user=True,
        )

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
            return _build_mapping(
                field=field,
                value=False,
                source="user_approval_required",
                confidence="high",
                action="leave_unchecked",
                mapped=False,
                requires_user=True,
            )

    # ---------------------------------------------------------
    # UNKNOWN
    # ---------------------------------------------------------

    return _build_mapping(
        field=field,
        value=None,
        source=None,
        confidence="none",
        action="manual_review",
        mapped=False,
        requires_user=True,
    )


def map_application_fields(
    application_result,
    resume_extraction_result,
    original_resume_file_path=None,
):
    """
    CA-5: Build structured application data.

    Inputs:
        application_result:
            CA-2 application form inspection result.

        resume_extraction_result:
            CA-4 structured resume extraction result.

        original_resume_file_path:
            Absolute path to the user's original uploaded
            resume PDF.

    This function:
        - maps trusted resume information
        - identifies unresolved human fields
        - preserves the original resume path
        - never invents values
        - never fills the browser
        - never submits an application
    """

    # ---------------------------------------------------------
    # Validate application inspection
    # ---------------------------------------------------------

    if not isinstance(
        application_result,
        dict,
    ):
        return {
            "status": "error",
            "message": (
                "Invalid application inspection result."
            ),
            "mappings": [],
        }

    if application_result.get(
        "status"
    ) != "success":
        return {
            "status": "error",
            "message": (
                application_result.get(
                    "message"
                )
                or
                "Application inspection failed."
            ),
            "mappings": [],
        }

    # ---------------------------------------------------------
    # Validate resume extraction
    # ---------------------------------------------------------

    if not isinstance(
        resume_extraction_result,
        dict,
    ):
        return {
            "status": "error",
            "message": (
                "Invalid resume extraction result."
            ),
            "mappings": [],
        }

    if resume_extraction_result.get(
        "status"
    ) != "success":
        return {
            "status": "error",
            "message": (
                resume_extraction_result.get(
                    "message"
                )
                or
                "Resume extraction failed."
            ),
            "mappings": [],
        }

    quality = resume_extraction_result.get(
        "quality"
    )

    if not isinstance(quality, dict):
        return {
            "status": "error",
            "message": (
                "Resume quality information "
                "is missing."
            ),
            "mappings": [],
        }

    if not quality.get(
        "can_use_for_application_mapping",
        False,
    ):
        return {
            "status": "error",
            "message": (
                "Resume is not ready for "
                "application mapping."
            ),
            "mappings": [],
        }

    resume = resume_extraction_result.get(
        "resume"
    )

    if not isinstance(
        resume,
        dict,
    ):
        return {
            "status": "error",
            "message": (
                "Structured resume data is missing."
            ),
            "mappings": [],
        }

    fields = application_result.get(
        "fields",
        [],
    )

    if not isinstance(
        fields,
        list,
    ):
        fields = []

    # ---------------------------------------------------------
    # Map every detected application field
    # ---------------------------------------------------------

    mappings = [
        _map_field(
            field=field,
            resume=resume,
            original_resume_file_path=(
                original_resume_file_path
            ),
        )
        for field in fields
    ]

    # ---------------------------------------------------------
    # Categorize mappings
    # ---------------------------------------------------------

    mapped_count = sum(
        1
        for item in mappings
        if item.get("mapped")
    )

    manual_review_count = sum(
        1
        for item in mappings
        if item.get("action")
        == "manual_review"
    )

    resume_upload_count = sum(
        1
        for item in mappings
        if item.get("action")
        == "upload"
    )

    unresolved_user_fields = [
        item
        for item in mappings
        if item.get("requires_user")
    ]

    approval_required_fields = [
        item
        for item in mappings
        if item.get("source")
        == "user_approval_required"
    ]

    unresolved_required_fields = [
        item
        for item in mappings
        if (
            item.get("field", {}).get(
                "required",
                False,
            )
            and (
                item.get("requires_user")
                or item.get("action")
                == "requires_resume_file"
            )
        )
    ]

    # ---------------------------------------------------------
    # CA-5 structured result
    # ---------------------------------------------------------

    return {
        "status": "success",
        "stage": "application_mapping",
        "application_url": application_result.get(
            "application_url"
        ),
        "page_url": application_result.get(
            "final_url"
        ),
        "resume_file_id": (
            resume_extraction_result.get(
                "file_id"
            )
        ),
        "original_resume_file_path": (
            original_resume_file_path
        ),
        "total_fields": len(fields),
        "mapped_fields": mapped_count,
        "manual_review_fields": (
            manual_review_count
        ),
        "resume_upload_fields": (
            resume_upload_count
        ),
        "unresolved_user_fields": (
            len(unresolved_user_fields)
        ),
        "approval_required_fields": (
            len(approval_required_fields)
        ),
        "unresolved_required_fields": (
            len(unresolved_required_fields)
        ),
        "ready_for_user_review": (
            len(unresolved_required_fields) == 0
        ),
        "mappings": mappings,
    }