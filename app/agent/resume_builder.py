from app.agent.career_profile import load_profile


def _clean_list(values):
    if not isinstance(values, list):
        return []

    return [
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    ]


def _all_profile_skills(profile):
    """
    Collect every real skill from the career profile.
    """

    skills = []

    skill_groups = profile.get("skills", {})

    if not isinstance(skill_groups, dict):
        return skills

    for values in skill_groups.values():

        if not isinstance(values, list):
            continue

        for skill in values:

            if isinstance(skill, str):
                skill = skill.strip()

                if skill and skill not in skills:
                    skills.append(skill)

    return skills


def _technology_names(job):
    """
    Extract technology names from the analyzed job.
    """

    technologies = []

    for field in [
        "required_skills",
        "preferred_skills",
        "tech_stack",
    ]:

        values = job.get(field, [])

        if not isinstance(values, list):
            continue

        for value in values:

            if not isinstance(value, str):
                continue

            value = value.strip()

            if value and value not in technologies:
                technologies.append(value)

    return technologies


def select_relevant_skills(profile, job, match_result):
    """
    Select only skills that actually exist in the
    candidate profile.

    The job can influence which real skills are
    prioritized, but cannot introduce new skills.
    """

    profile_skills = _all_profile_skills(profile)

    if not profile_skills:
        return []

    selected = []

    skills_data = match_result.get("skills", {})

    for category in [
        "required",
        "preferred",
        "technology_stack",
    ]:

        category_data = skills_data.get(
            category,
            {},
        )

        matched = category_data.get(
            "matched",
            [],
        )

        if not isinstance(matched, list):
            continue

        for matched_skill in matched:

            for profile_skill in profile_skills:

                if (
                    profile_skill.lower()
                    == str(matched_skill).lower()
                ):

                    if profile_skill not in selected:
                        selected.append(profile_skill)

    # Also preserve important real skills relevant
    # to the candidate's preferred roles.

    job_text = " ".join(
        str(value)
        for value in _technology_names(job)
    ).lower()

    for skill in profile_skills:

        if skill.lower() in job_text:

            if skill not in selected:
                selected.append(skill)

    return selected


def select_projects(profile, match_result, limit=3):
    """
    Select real projects from the profile.

    Projects are NEVER created here.
    """

    projects = profile.get(
        "projects",
        [],
    )

    if not isinstance(projects, list):
        return []

    scored = []

    matched_technologies = set()

    skills_data = match_result.get(
        "skills",
        {},
    )

    for category in [
        "required",
        "preferred",
        "technology_stack",
    ]:

        category_data = skills_data.get(
            category,
            {},
        )

        matched = category_data.get(
            "matched",
            [],
        )

        if isinstance(matched, list):

            for skill in matched:
                matched_technologies.add(
                    str(skill).lower()
                )

    for project in projects:

        if not isinstance(project, dict):
            continue

        technologies = project.get(
            "technologies",
            [],
        )

        if not isinstance(technologies, list):
            technologies = []

        score = 0

        for technology in technologies:

            if (
                str(technology).lower()
                in matched_technologies
            ):
                score += 1

        scored.append(
            (
                score,
                project,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        project
        for _, project in scored[:limit]
    ]


def build_grounded_resume(
    profile,
    job,
    match_result,
):
    """
    Build a resume draft using ONLY information
    contained in the career profile.

    The job description controls relevance,
    not factual content.
    """

    personal = profile.get(
        "personal",
        {},
    )

    links = profile.get(
        "professional_links",
        {},
    )

    experience = profile.get(
        "experience",
        [],
    )

    education = profile.get(
        "education",
        [],
    )

    certifications = profile.get(
        "certifications",
        [],
    )

    achievements = profile.get(
        "achievements",
        [],
    )

    selected_skills = select_relevant_skills(
        profile,
        job,
        match_result,
    )

    selected_projects = select_projects(
        profile,
        match_result,
    )

    return {
        "target": {
            "company": job.get(
                "company"
            ),
            "position": job.get(
                "position"
            ),
            "source_url": job.get(
                "application_url"
            ),
        },

        "candidate": {
            "full_name": personal.get(
                "full_name",
                "",
            ),
            "email": personal.get(
                "email",
                "",
            ),
            "phone": personal.get(
                "phone",
                "",
            ),
            "location": personal.get(
                "location",
                "",
            ),
        },

        "professional_links": {
            "github": links.get(
                "github",
                "",
            ),
            "linkedin": links.get(
                "linkedin",
                "",
            ),
            "portfolio": links.get(
                "portfolio",
                "",
            ),
        },

        "skills": selected_skills,

        "experience": experience,

        "projects": selected_projects,

        "education": education,

        "certifications": _clean_list(
            certifications
        ),

        "achievements": _clean_list(
            achievements
        ),

        "grounding": {
            "source": "career_profile",
            "job_used_for": [
                "skill prioritization",
                "project prioritization",
                "resume targeting",
            ],
            "facts_created_by_ai": False,
        },
    }


def build_from_current_profile(
    job,
    match_result,
):
    """
    Convenience function used by the agent.
    """

    profile = load_profile()

    return build_grounded_resume(
        profile=profile,
        job=job,
        match_result=match_result,
    )