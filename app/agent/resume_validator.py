import re

from app.agent.career_profile import load_profile


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize(value):

    if not isinstance(value, str):
        return ""

    return (
        value.lower()
        .strip()
        .replace("–", "-")
        .replace("—", "-")
    )


# ==========================================================
# TEXT MATCHING
# ==========================================================

def text_contains(source, target):

    source = normalize(source)
    target = normalize(target)

    if not source or not target:
        return False

    pattern = (
        r"(?<![a-zA-Z0-9])"
        + re.escape(target)
        + r"(?![a-zA-Z0-9])"
    )

    return re.search(
        pattern,
        source,
    ) is not None


# ==========================================================
# PROFILE SKILLS
# ==========================================================

def get_profile_skills(profile):

    skills = set()

    for category_values in profile.get(
        "skills",
        {},
    ).values():

        if not isinstance(category_values, list):
            continue

        for skill in category_values:

            if isinstance(skill, str):

                skills.add(
                    normalize(skill)
                )

    return skills


# ==========================================================
# PROFILE PROJECTS
# ==========================================================

def get_profile_projects(profile):

    projects = {}

    for project in profile.get(
        "projects",
        [],
    ):

        name = normalize(
            project.get(
                "name",
                "",
            )
        )

        if name:
            projects[name] = project

    return projects


# ==========================================================
# PROFILE EXPERIENCE
# ==========================================================

def get_profile_experience(profile):

    experience = {}

    for item in profile.get(
        "experience",
        [],
    ):

        key = (
            normalize(
                item.get(
                    "company",
                    "",
                )
            ),
            normalize(
                item.get(
                    "role",
                    "",
                )
            ),
        )

        experience[key] = item

    return experience


# ==========================================================
# CHECK PERSONAL INFORMATION
# ==========================================================

def validate_candidate(
    profile,
    resume,
):

    errors = []

    personal = profile.get(
        "personal",
        {},
    )

    candidate = resume.get(
        "candidate",
        {},
    )

    for field in [
        "full_name",
        "email",
        "phone",
        "location",
    ]:

        generated = normalize(
            candidate.get(
                field,
                "",
            )
        )

        actual = normalize(
            personal.get(
                field,
                "",
            )
        )

        if generated and actual:

            if generated != actual:

                errors.append(
                    f"Candidate {field} "
                    "does not match profile."
                )

    return errors


# ==========================================================
# CHECK PROFESSIONAL LINKS
# ==========================================================

def validate_professional_links(
    profile,
    resume,
):

    errors = []

    actual = profile.get(
        "professional_links",
        {},
    )

    generated = resume.get(
        "professional_links",
        {},
    )

    for field in [
        "github",
        "linkedin",
        "portfolio",
    ]:

        generated_value = normalize(
            generated.get(
                field,
                "",
            )
        )

        actual_value = normalize(
            actual.get(
                field,
                "",
            )
        )

        if not generated_value:
            continue

        if generated_value != actual_value:

            errors.append(
                f"Unsupported professional link: "
                f"{field}"
            )

    return errors


# ==========================================================
# CHECK SKILLS
# ==========================================================

def validate_skills(
    profile,
    resume,
):

    errors = []

    profile_skills = get_profile_skills(
        profile
    )

    generated_skills = resume.get(
        "skills",
        [],
    )

    for item in generated_skills:

        # New resume format:
        #
        # {
        #     "skill": "Python",
        #     "category": "..."
        # }

        if isinstance(item, dict):

            skill = item.get(
                "skill",
                "",
            )

        elif isinstance(item, str):

            skill = item

        else:

            continue

        normalized_skill = normalize(
            skill
        )

        if not normalized_skill:
            continue

        if normalized_skill in profile_skills:
            continue

        matched = False

        for profile_skill in profile_skills:

            if normalized_skill == profile_skill:

                matched = True
                break

        if not matched:

            errors.append(
                f"Unsupported skill: {skill}"
            )

    return errors


# ==========================================================
# CHECK EXPERIENCE
# ==========================================================

def validate_experience(
    profile,
    resume,
):

    errors = []

    profile_experience = (
        get_profile_experience(
            profile
        )
    )

    for item in resume.get(
        "experience",
        [],
    ):

        company = normalize(
            item.get(
                "company",
                "",
            )
        )

        role = normalize(
            item.get(
                "role",
                "",
            )
        )

        key = (
            company,
            role,
        )

        if key not in profile_experience:

            errors.append(
                "Unsupported experience entry: "
                f"{item.get('company', '')} - "
                f"{item.get('role', '')}"
            )

            continue

        original = profile_experience[key]

        # --------------------------------------------------
        # Location
        # --------------------------------------------------

        generated_location = normalize(
            item.get(
                "location",
                "",
            )
        )

        original_location = normalize(
            original.get(
                "location",
                "",
            )
        )

        if (
            generated_location
            and generated_location
            != original_location
        ):

            errors.append(
                f"Experience location does not "
                f"match for {item.get('company', '')}."
            )

        # --------------------------------------------------
        # Start date
        # --------------------------------------------------

        generated_start = normalize(
            item.get(
                "start_date",
                "",
            )
        )

        original_start = normalize(
            original.get(
                "start_date",
                "",
            )
        )

        if (
            generated_start
            and generated_start
            != original_start
        ):

            errors.append(
                f"Experience start date does not "
                f"match for {item.get('company', '')}."
            )

        # --------------------------------------------------
        # End date
        # --------------------------------------------------

        generated_end = normalize(
            item.get(
                "end_date",
                "",
            )
        )

        original_end = normalize(
            original.get(
                "end_date",
                "",
            )
        )

        if (
            generated_end
            and generated_end
            != original_end
        ):

            errors.append(
                f"Experience end date does not "
                f"match for {item.get('company', '')}."
            )

        # --------------------------------------------------
        # Responsibilities
        #
        # Every generated responsibility must be
        # supported by the original experience.
        # --------------------------------------------------

        original_responsibilities = [
            normalize(value)
            for value in original.get(
                "responsibilities",
                [],
            )
            if isinstance(value, str)
        ]

        generated_responsibilities = (
            item.get(
                "responsibilities",
                [],
            )
        )

        for responsibility in (
            generated_responsibilities
        ):

            if not isinstance(
                responsibility,
                str,
            ):
                continue

            generated_text = normalize(
                responsibility
            )

            if not generated_text:
                continue

            supported = False

            for original_text in (
                original_responsibilities
            ):

                if (
                    generated_text
                    == original_text
                    or generated_text
                    in original_text
                    or original_text
                    in generated_text
                ):

                    supported = True
                    break

            if not supported:

                errors.append(
                    "Unsupported experience "
                    "responsibility: "
                    f"{responsibility}"
                )

    return errors


# ==========================================================
# CHECK PROJECTS
# ==========================================================

def validate_projects(
    profile,
    resume,
):

    errors = []

    profile_projects = (
        get_profile_projects(
            profile
        )
    )

    for project in resume.get(
        "projects",
        [],
    ):

        name = normalize(
            project.get(
                "name",
                "",
            )
        )

        if name not in profile_projects:

            errors.append(
                "Unsupported project: "
                f"{project.get('name', '')}"
            )

            continue

        original = profile_projects[
            name
        ]

        # --------------------------------------------------
        # Technologies
        # --------------------------------------------------

        original_technologies = {
            normalize(
                technology
            )
            for technology in original.get(
                "technologies",
                [],
            )
            if isinstance(
                technology,
                str,
            )
        }

        generated_technologies = (
            project.get(
                "technologies",
                [],
            )
        )

        for technology in generated_technologies:

            if not isinstance(
                technology,
                str,
            ):
                continue

            if (
                normalize(technology)
                not in original_technologies
            ):

                errors.append(
                    f"Unsupported technology "
                    f"'{technology}' in project "
                    f"'{project.get('name', '')}'."
                )

        # --------------------------------------------------
        # Description
        #
        # The generated description must be
        # supported by the original description.
        # --------------------------------------------------

        original_description = normalize(
            original.get(
                "description",
                "",
            )
        )

        generated_description = normalize(
            project.get(
                "description",
                "",
            )
        )

        if generated_description:

            if not original_description:

                errors.append(
                    f"Unsupported project description "
                    f"for '{project.get('name', '')}'."
                )

            else:

                # The safest first version is to require
                # the generated description to be based
                # on the original description.
                #
                # We allow the original description to
                # contain the generated text or vice versa.

                if not (
                    generated_description
                    == original_description
                    or generated_description
                    in original_description
                    or original_description
                    in generated_description
                ):

                    errors.append(
                        f"Unsupported project description "
                        f"for '{project.get('name', '')}'."
                    )

    return errors


# ==========================================================
# CHECK EDUCATION
# ==========================================================

def validate_education(
    profile,
    resume,
):

    errors = []

    profile_education = profile.get(
        "education",
        [],
    )

    generated_education = resume.get(
        "education",
        [],
    )

    for item in generated_education:

        matched_original = None

        for original in profile_education:

            same_institution = (
                normalize(
                    item.get(
                        "institution",
                        "",
                    )
                )
                == normalize(
                    original.get(
                        "institution",
                        "",
                    )
                )
            )

            same_degree = (
                normalize(
                    item.get(
                        "degree",
                        "",
                    )
                )
                == normalize(
                    original.get(
                        "degree",
                        "",
                    )
                )
            )

            if (
                same_institution
                and same_degree
            ):

                matched_original = original
                break

        if matched_original is None:

            errors.append(
                "Unsupported education entry: "
                f"{item.get('institution', '')}"
            )

            continue

        # --------------------------------------------------
        # Check every important education field
        # --------------------------------------------------

        fields = [
            "degree",
            "field",
            "institution",
            "location",
            "start_year",
            "end_year",
            "cgpa",
        ]

        for field in fields:

            generated_value = normalize(
                item.get(
                    field,
                    "",
                )
            )

            actual_value = normalize(
                matched_original.get(
                    field,
                    "",
                )
            )

            if not generated_value:
                continue

            if generated_value != actual_value:

                errors.append(
                    f"Education {field} does not "
                    "match profile."
                )

    return errors


# ==========================================================
# CHECK CERTIFICATIONS
# ==========================================================

def validate_certifications(
    profile,
    resume,
):

    errors = []

    actual = {
        normalize(certification)
        for certification in profile.get(
            "certifications",
            [],
        )
        if isinstance(
            certification,
            str,
        )
    }

    for certification in resume.get(
        "certifications",
        [],
    ):

        if not isinstance(
            certification,
            str,
        ):
            continue

        normalized = normalize(
            certification
        )

        if normalized not in actual:

            errors.append(
                f"Unsupported certification: "
                f"{certification}"
            )

    return errors


# ==========================================================
# CHECK ACHIEVEMENTS
# ==========================================================

def validate_achievements(
    profile,
    resume,
):

    errors = []

    actual = {
        normalize(achievement)
        for achievement in profile.get(
            "achievements",
            [],
        )
        if isinstance(
            achievement,
            str,
        )
    }

    for achievement in resume.get(
        "achievements",
        [],
    ):

        if not isinstance(
            achievement,
            str,
        ):
            continue

        generated = normalize(
            achievement
        )

        if not generated:
            continue

        # --------------------------------------------------
        # ACHIEVEMENTS MUST BE EXACT
        # --------------------------------------------------

        if generated not in actual:

            errors.append(
                f"Unsupported achievement: "
                f"{achievement}"
            )

    return errors


# ==========================================================
# CHECK SUMMARY
# ==========================================================

def validate_summary(
    profile,
    resume,
):

    errors = []

    summary = normalize(
        resume.get(
            "summary",
            "",
        )
    )

    if not summary:
        return errors

    profile_text_parts = []

    # --------------------------------------------------
    # Personal
    # --------------------------------------------------

    personal = profile.get(
        "personal",
        {},
    )

    for value in personal.values():

        if isinstance(value, str):
            profile_text_parts.append(
                normalize(value)
            )

    # --------------------------------------------------
    # Skills
    # --------------------------------------------------

    profile_skills = get_profile_skills(
        profile
    )

    profile_text_parts.extend(
        profile_skills
    )

    # --------------------------------------------------
    # Roles
    # --------------------------------------------------

    for role in profile.get(
        "preferred_roles",
        [],
    ):

        if isinstance(role, str):

            profile_text_parts.append(
                normalize(role)
            )

    # --------------------------------------------------
    # Experience
    # --------------------------------------------------

    for experience in profile.get(
        "experience",
        [],
    ):

        for value in experience.values():

            if isinstance(value, str):

                profile_text_parts.append(
                    normalize(value)
                )

            elif isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        profile_text_parts.append(
                            normalize(item)
                        )

    # --------------------------------------------------
    # Projects
    # --------------------------------------------------

    for project in profile.get(
        "projects",
        [],
    ):

        for value in project.values():

            if isinstance(value, str):

                profile_text_parts.append(
                    normalize(value)
                )

            elif isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        profile_text_parts.append(
                            normalize(item)
                        )

    # --------------------------------------------------
    # Education
    # --------------------------------------------------

    for education in profile.get(
        "education",
        [],
    ):

        for value in education.values():

            if isinstance(value, str):

                profile_text_parts.append(
                    normalize(value)
                )

            elif isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        profile_text_parts.append(
                            normalize(item)
                        )

    # --------------------------------------------------
    # Certifications
    # --------------------------------------------------

    for certification in profile.get(
        "certifications",
        [],
    ):

        if isinstance(
            certification,
            str,
        ):

            profile_text_parts.append(
                normalize(certification)
            )

    # --------------------------------------------------
    # Achievements
    # --------------------------------------------------

    for achievement in profile.get(
        "achievements",
        [],
    ):

        if isinstance(
            achievement,
            str,
        ):

            profile_text_parts.append(
                normalize(achievement)
            )

    # --------------------------------------------------
    # Detect suspicious claims
    #
    # We don't require every summary word to exist
    # literally in the profile because summaries are
    # naturally rewritten.
    #
    # Instead, block common unsupported claims when
    # the underlying evidence is completely absent.
    # --------------------------------------------------

    suspicious_claims = [
        (
            "expert",
            "expertise"
        ),
        (
            "senior",
            "senior"
        ),
        (
            "lead",
            "leadership"
        ),
        (
            "professional experience",
            "experience"
        ),
    ]

    for phrase, evidence in suspicious_claims:

        if phrase not in summary:
            continue

        evidence_exists = any(
            evidence in text
            for text in profile_text_parts
        )

        if not evidence_exists:

            errors.append(
                f"Unsupported summary claim: "
                f"'{phrase}'"
            )

    return errors


# ==========================================================
# MAIN VALIDATOR
# ==========================================================

def validate_resume(
    resume,
):

    profile = load_profile()

    errors = []

    errors.extend(
        validate_candidate(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_professional_links(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_skills(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_experience(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_projects(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_education(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_certifications(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_achievements(
            profile,
            resume,
        )
    )

    errors.extend(
        validate_summary(
            profile,
            resume,
        )
    )

    return {
        "status": (
            "valid"
            if not errors
            else "invalid"
        ),

        "valid": not errors,

        "errors": errors,

        "error_count": len(errors),
    }