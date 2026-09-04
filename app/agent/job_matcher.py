import re

from app.agent.career_profile import load_profile
from app.agent.experience_evaluator import evaluate_experience


# ============================================================
# TECHNOLOGY ALIASES
# ============================================================

TECH_ALIASES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",

    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",

    "typescript": "typescript",

    "javascript": "javascript",

    "aws": "aws",

    "rust": "rust",

    "redis": "redis",

    "terraform": "terraform",

    "solidjs": "solidjs",

    "timescaledb": "timescaledb",

    "rds": "rds",
    "ecs": "ecs",
    "elasticache": "elasticache",

    "mysql": "mysql",
    "mongodb": "mongodb",

    "fastapi": "fastapi",

    "react": "react.js",
    "react.js": "react.js",

    "python": "python",

    "java": "java",

    "c++": "c++",
    "c": "c",
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    """
    Normalize text safely for matching.

    None is treated as an empty string.
    This prevents missing job information from
    crashing the matching pipeline.
    """

    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    return (
        text.lower()
        .strip()
        .replace("-", " ")
        .replace("_", " ")
    )


# ============================================================
# CANONICAL SKILL
# ============================================================

def canonical_skill(skill):
    """
    Convert a skill into its canonical form.
    """

    skill = normalize(skill)

    return TECH_ALIASES.get(
        skill,
        skill,
    )


# ============================================================
# SKILL TOKEN MATCHING
# ============================================================

def contains_skill(text, skill):
    """
    Check whether a skill exists as a complete token.

    This prevents cases such as:

        C matching C++

    or:

        C matching TypeScript
    """

    text = normalize(text)
    skill = normalize(skill)

    if not text or not skill:
        return False

    pattern = (
        r"(?<![a-zA-Z0-9])"
        + re.escape(skill)
        + r"(?![a-zA-Z0-9])"
    )

    return re.search(
        pattern,
        text,
    ) is not None


# ============================================================
# PROFILE SKILLS
# ============================================================

def get_profile_skills(profile):
    """
    Return the candidate's skills as a normalized set.

    Using a set automatically removes duplicates.
    """

    skills = set()

    profile_skill_groups = profile.get(
        "skills",
        {},
    )

    if not isinstance(
        profile_skill_groups,
        dict,
    ):
        return skills

    for values in profile_skill_groups.values():

        if not isinstance(values, list):
            continue

        for value in values:

            if not isinstance(
                value,
                str,
            ):
                continue

            normalized = canonical_skill(
                value
            )

            if normalized:
                skills.add(
                    normalized
                )

    return skills


# ============================================================
# EXTRACT JOB TECHNICAL SKILLS
# ============================================================

def extract_technical_skills(
    job,
    field_names,
):
    """
    Extract known technical skills from
    the requested job fields.

    Returns a set, so duplicates are removed.
    """

    found = set()

    if not isinstance(job, dict):
        return found

    for field in field_names:

        values = job.get(
            field,
            [],
        )

        if not isinstance(
            values,
            list,
        ):
            continue

        for value in values:

            if not isinstance(
                value,
                str,
            ):
                continue

            text = normalize(
                value
            )

            if not text:
                continue

            for name in TECH_ALIASES:

                if contains_skill(
                    text,
                    name,
                ):

                    found.add(
                        TECH_ALIASES[name]
                    )

    return found


# ============================================================
# SKILL MATCH
# ============================================================

def calculate_skill_match(
    profile_skills,
    job_skills,
):
    """
    Compare profile skills with job skills.

    If the job does not specify any skills,
    score is None rather than 0.

    None means:
        Not specified

    0 means:
        Specified, but nothing matched.
    """

    if not job_skills:

        return (
            None,
            [],
            [],
        )

    matched = sorted(
        set(
            profile_skills.intersection(
                job_skills
            )
        )
    )

    missing = sorted(
        set(
            job_skills.difference(
                profile_skills
            )
        )
    )

    score = (
        len(matched)
        / len(job_skills)
    ) * 100

    return (
        round(score),
        matched,
        missing,
    )


# ============================================================
# ROLE MATCH
# ============================================================

def calculate_role_match(
    profile,
    job,
):
    """
    Compare the job position against the
    candidate's preferred roles.

    Returns:
        None -> no preference specified
        100  -> preferred role matched
        0    -> preference exists but did not match
    """

    if not isinstance(
        profile,
        dict,
    ):
        return None

    if not isinstance(
        job,
        dict,
    ):
        return None

    position = normalize(
        job.get(
            "position",
            "",
        )
    )

    preferred_roles = profile.get(
        "preferred_roles",
        [],
    )

    if not isinstance(
        preferred_roles,
        list,
    ):
        return None

    preferred_roles = [
        normalize(role)
        for role in preferred_roles
        if normalize(role)
    ]

    # Candidate has not specified preferred roles.
    if not preferred_roles:
        return None

    # Job position is unavailable.
    if not position:
        return None

    for role in preferred_roles:

        if role in position:

            return 100

    return 0


# ============================================================
# LOCATION MATCH
# ============================================================

def calculate_location_match(
    profile,
    job,
):
    """
    Compare candidate location preferences
    with the job location.

    Returns:
        None -> information not specified
        100  -> location matches
        0    -> both sides are known but don't match
    """

    if not isinstance(
        profile,
        dict,
    ):
        return None

    if not isinstance(
        job,
        dict,
    ):
        return None

    preferred_locations = profile.get(
        "preferred_locations",
        [],
    )

    if not isinstance(
        preferred_locations,
        list,
    ):
        return None

    preferred_locations = [
        normalize(location)
        for location in preferred_locations
        if normalize(location)
    ]

    # Candidate did not specify location preferences.
    if not preferred_locations:
        return None

    job_location = normalize(
        job.get(
            "location",
            "",
        )
    )

    # Job did not specify location.
    if not job_location:
        return None

    # Candidate accepts anywhere.
    if "anywhere" in preferred_locations:
        return 100

    for location in preferred_locations:

        if location in job_location:
            return 100

    return 0


# ============================================================
# WORK MODE MATCH
# ============================================================

def calculate_work_mode_match(
    profile,
    job,
):
    """
    Compare candidate work-mode preferences
    with the job work mode.

    Returns:
        None -> information not specified
        100  -> preference matches
        0    -> preference exists but does not match
    """

    if not isinstance(
        profile,
        dict,
    ):
        return None

    if not isinstance(
        job,
        dict,
    ):
        return None

    work_mode = normalize(
        job.get(
            "work_mode",
            "",
        )
    )

    preferences = profile.get(
        "preferences",
        {},
    )

    if not isinstance(
        preferences,
        dict,
    ):
        return None

    # Job did not specify work mode.
    if not work_mode:
        return None

    # --------------------------------------------------------
    # Remote
    # --------------------------------------------------------

    if work_mode in [
        "remote",
        "remote friendly",
        "remote-friendly",
    ]:

        if preferences.get(
            "remote",
            False,
        ):
            return 100

        # If candidate has explicitly configured
        # work-mode preferences but remote is false,
        # this is an actual mismatch.
        if any(
            key in preferences
            for key in [
                "remote",
                "hybrid",
                "onsite",
            ]
        ):
            return 0

        return None

    # --------------------------------------------------------
    # Hybrid
    # --------------------------------------------------------

    if work_mode == "hybrid":

        if preferences.get(
            "hybrid",
            False,
        ):
            return 100

        if any(
            key in preferences
            for key in [
                "remote",
                "hybrid",
                "onsite",
            ]
        ):
            return 0

        return None

    # --------------------------------------------------------
    # Onsite
    # --------------------------------------------------------

    if work_mode in [
        "onsite",
        "on site",
        "in office",
    ]:

        if preferences.get(
            "onsite",
            False,
        ):
            return 100

        if any(
            key in preferences
            for key in [
                "remote",
                "hybrid",
                "onsite",
            ]
        ):
            return 0

        return None

    # Unknown work-mode description.
    return None


# ============================================================
# MAIN MATCHING FUNCTION
# ============================================================

def match_job(job):

    """
    Compare the job against the candidate's
    verified career profile.

    This function does NOT create or modify
    candidate facts.
    """

    if not isinstance(
        job,
        dict,
    ):
        return {
            "status": "error",
            "error": "Invalid job data.",
        }

    profile = load_profile()

    profile_skills = get_profile_skills(
        profile
    )

    # ========================================================
    # EXTRACT JOB SKILLS
    # ========================================================

    required_skills = extract_technical_skills(
        job,
        [
            "required_skills",
        ],
    )

    preferred_skills = extract_technical_skills(
        job,
        [
            "preferred_skills",
        ],
    )

    stack_skills = extract_technical_skills(
        job,
        [
            "tech_stack",
        ],
    )

    # ========================================================
    # REQUIRED SKILLS
    # ========================================================

    (
        required_score,
        required_matched,
        required_missing,
    ) = calculate_skill_match(
        profile_skills,
        required_skills,
    )

    # ========================================================
    # PREFERRED SKILLS
    # ========================================================

    (
        preferred_score,
        preferred_matched,
        preferred_missing,
    ) = calculate_skill_match(
        profile_skills,
        preferred_skills,
    )

    # ========================================================
    # TECHNOLOGY STACK
    # ========================================================

    (
        stack_score,
        stack_matched,
        stack_missing,
    ) = calculate_skill_match(
        profile_skills,
        stack_skills,
    )

    # ========================================================
    # OTHER MATCHING FACTORS
    # ========================================================

    role_score = calculate_role_match(
        profile,
        job,
    )

    location_score = calculate_location_match(
        profile,
        job,
    )

    work_mode_score = calculate_work_mode_match(
        profile,
        job,
    )

    experience_analysis = evaluate_experience(
        profile,
        job,
    )

    # ========================================================
    # DYNAMIC OVERALL SCORE
    # ========================================================
    #
    # Required technical skills: 45%
    # Preferred skills:           15%
    # Technology stack:           10%
    # Role:                       15%
    # Location:                  7.5%
    # Work mode:                 7.5%
    #
    # Categories that are not specified
    # are removed from the calculation.
    # ========================================================

    components = []

    if required_score is not None:

        components.append(
            (
                required_score,
                0.45,
            )
        )

    if preferred_score is not None:

        components.append(
            (
                preferred_score,
                0.15,
            )
        )

    if stack_score is not None:

        components.append(
            (
                stack_score,
                0.10,
            )
        )

    if role_score is not None:

        components.append(
            (
                role_score,
                0.15,
            )
        )

    if location_score is not None:

        components.append(
            (
                location_score,
                0.075,
            )
        )

    if work_mode_score is not None:

        components.append(
            (
                work_mode_score,
                0.075,
            )
        )

    # --------------------------------------------------------
    # Calculate normalized score
    # --------------------------------------------------------

    if components:

        total_weight = sum(
            weight
            for score, weight in components
        )

        overall_score = round(
            sum(
                score * weight
                for score, weight in components
            )
            / total_weight
        )

    else:

        overall_score = 0

    # ========================================================
    # RECOMMENDATION
    # ========================================================

    if overall_score >= 80:

        recommendation = "Strong match"

    elif overall_score >= 60:

        recommendation = "Moderate match"

    elif overall_score >= 40:

        recommendation = "Weak match"

    else:

        recommendation = "Poor match"

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        "status": "success",

        "overall_score": overall_score,

        "recommendation": recommendation,

        "role_score": role_score,

        "location_score": location_score,

        "work_mode_score": work_mode_score,

        "skills": {

            "required": {

                "score": required_score,

                "matched": sorted(
                    set(
                        required_matched
                    )
                ),

                "missing": sorted(
                    set(
                        required_missing
                    )
                ),
            },

            "preferred": {

                "score": preferred_score,

                "matched": sorted(
                    set(
                        preferred_matched
                    )
                ),

                "missing": sorted(
                    set(
                        preferred_missing
                    )
                ),
            },

            "technology_stack": {

                "score": stack_score,

                "matched": sorted(
                    set(
                        stack_matched
                    )
                ),

                "missing": sorted(
                    set(
                        stack_missing
                    )
                ),
            },
        },

        "experience": experience_analysis,
    }