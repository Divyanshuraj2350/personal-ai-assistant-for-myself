from app.agent.career_profile import load_profile


# ============================================================
# TECHNOLOGY ALIASES
# ============================================================

TECH_ALIASES = {
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",

    "postgres": "postgresql",
    "postgresql": "postgresql",

    "react": "react.js",
    "reactjs": "react.js",
    "react.js": "react.js",

    "javascript": "javascript",
    "typescript": "typescript",

    "python": "python",
    "java": "java",
    "c++": "c++",
    "c": "c",

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

    "solidity": "solidity",
    "ethereum": "ethereum",
    "ethers.js": "ethers.js",

    "rest": "rest",
    "rest api": "rest apis",
    "rest apis": "rest apis",
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(value):
    """
    Safely normalize a value for comparison.

    Job descriptions can contain missing/null fields.
    Never call string methods directly on None.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip().lower()

    return str(value).strip().lower()


def canonical(value):
    """
    Return a safe canonical representation of a value.
    """

    value = normalize(value)

    if not value:
        return ""

    return (
        value
        .replace(".", "")
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .strip()
    )


# ============================================================
# CLEANING
# ============================================================

def clean_list(values):
    """
    Clean a list while safely ignoring None values.
    """

    if not isinstance(values, list):
        return []

    cleaned = []

    for value in values:

        if value is None:
            continue

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        if value:
            cleaned.append(value)

    return cleaned


# ============================================================
# PROFILE SKILLS
# ============================================================

def get_profile_skills(profile):

    skills = []

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

        for skill in values:

            if not isinstance(skill, str):
                continue

            skill = skill.strip()

            if not skill:
                continue

            if skill not in skills:
                skills.append(skill)

    return skills


# ============================================================
# JOB TECHNOLOGY EXTRACTION
# ============================================================

def extract_atomic_technologies(value):
    """
    Convert compound job strings into individual technologies.

    Example:

    "backend: typescript, node.js, redis, postgres"

    becomes:

    typescript
    node.js
    redis
    postgresql
    """

    if not isinstance(value, str):
        return []

    text = normalize(value)

    prefixes = [
        "frontend:",
        "backend:",
        "infrastructure:",
        "experience with",
        "familiarity with",
    ]

    for prefix in prefixes:

        if text.startswith(prefix):
            text = text[
                len(prefix):
            ].strip()

    text = (
        text
        .replace("(", ",")
        .replace(")", ",")
        .replace("/", ",")
    )

    text = text.replace(
        " and ",
        ",",
    )

    parts = []

    for part in text.split(","):

        part = part.strip()

        if not part:
            continue

        part = part.replace(
            "experience with ",
            "",
        ).strip()

        part = part.replace(
            "familiarity with ",
            "",
        ).strip()

        if part:
            parts.append(part)

    return parts


def get_job_requirement_groups(job):

    groups = {}

    for field in [
        "required_skills",
        "preferred_skills",
        "tech_stack",
    ]:

        values = job.get(
            field,
            [],
        )

        if not isinstance(values, list):
            values = []

        extracted = []

        for value in values:

            for technology in extract_atomic_technologies(
                value
            ):

                technology = canonical(
                    technology
                )

                if (
                    technology
                    and technology not in extracted
                ):

                    extracted.append(
                        technology
                    )

        groups[field] = extracted

    return groups


# ============================================================
# MATCHING
# ============================================================

def find_skill_match(
    profile_skills,
    job_skill,
):

    job_skill = canonical(
        job_skill
    )

    for profile_skill in profile_skills:

        if canonical(
            profile_skill
        ) == job_skill:

            return profile_skill

    return None


# ============================================================
# SKILL RANKING
# ============================================================

def rank_skills(
    profile,
    job,
    match_result,
):

    profile_skills = get_profile_skills(
        profile
    )

    groups = get_job_requirement_groups(
        job
    )

    ranked = {}

    # Direct required match.
    for job_skill in groups[
        "required_skills"
    ]:

        profile_skill = find_skill_match(
            profile_skills,
            job_skill,
        )

        if profile_skill:

            ranked.setdefault(
                profile_skill,
                0,
            )

            ranked[
                profile_skill
            ] += 300

    # Direct preferred match.
    for job_skill in groups[
        "preferred_skills"
    ]:

        profile_skill = find_skill_match(
            profile_skills,
            job_skill,
        )

        if profile_skill:

            ranked.setdefault(
                profile_skill,
                0,
            )

            ranked[
                profile_skill
            ] += 200

    # Direct technology stack match.
    for job_skill in groups[
        "tech_stack"
    ]:

        profile_skill = find_skill_match(
            profile_skills,
            job_skill,
        )

        if profile_skill:

            ranked.setdefault(
                profile_skill,
                0,
            )

            ranked[
                profile_skill
            ] += 150

    # Useful existing engineering skills.
    supporting_weights = {
        "fastapi": 100,
        "python": 100,
        "rest apis": 80,
        "javascript": 50,
        "git": 40,
        "linux/ubuntu": 30,
        "bash scripting": 30,
        "mongodb": 30,
        "mysql": 30,
        "java": 20,
        "c++": 20,
        "scikit-learn": 20,
        "python ml pipelines": 20,
        "service/daemon workflows": 20,
        "process management": 20,
        "github": 10,
    }

    for skill in profile_skills:

        weight = supporting_weights.get(
            canonical(skill),
            0,
        )

        if weight:

            ranked.setdefault(
                skill,
                0,
            )

            ranked[
                skill
            ] += weight

    ordered = sorted(
        ranked.items(),
        key=lambda item: (
            -item[1],
            item[0].lower(),
        ),
    )

    return [
        {
            "skill": skill,
            "priority": priority,
        }
        for skill, priority in ordered
    ]


# ============================================================
# PROJECT RELEVANCE
# ============================================================

def get_project_technologies(project):

    technologies = project.get(
        "technologies",
        [],
    )

    if not isinstance(
        technologies,
        list,
    ):
        return []

    return [
        canonical(technology)
        for technology in technologies
        if isinstance(
            technology,
            str,
        )
    ]


def get_project_role_relevance(
    project,
    job,
):
    """
    Determine broad role relevance.

    This is deliberately weaker than direct technology
    matching.
    """

    name = normalize(
        project.get(
            "name",
            "",
        )
    )

    description = normalize(
        project.get(
            "description",
            "",
        )
    )

    text = (
        name
        + " "
        + description
    )

    position = normalize(
        job.get(
            "position",
            "",
        )
    )

    score = 0
    reasons = []

    # Backend / API relevance.
    backend_terms = [
        "backend",
        "api",
        "fastapi",
        "node.js",
        "server",
        "rest",
        "authentication",
    ]

    if any(
        term in text
        for term in backend_terms
    ):

        if (
            "backend" in position
            or "software engineer" in position
            or "developer" in position
        ):

            score += 15
            reasons.append(
                "backend/software-engineering relevance"
            )

    # Automation relevance.
    if (
        "automation" in text
        or "automate" in text
    ):

        score += 10

        reasons.append(
            "automation relevance"
        )

    # Security relevance.
    if (
        "security" in text
        or "authentication" in text
    ):

        score += 5

        reasons.append(
            "security relevance"
        )

    return score, reasons


def score_project(
    project,
    job,
):
    """
    Calculate project relevance using three layers:

    1. Direct technology overlap
    2. Strong role relevance
    3. Supporting relevance

    Technology overlap always dominates.
    """

    technologies = get_project_technologies(
        project
    )

    groups = get_job_requirement_groups(
        job
    )

    required = set(
        groups[
            "required_skills"
        ]
    )

    preferred = set(
        groups[
            "preferred_skills"
        ]
    )

    stack = set(
        groups[
            "tech_stack"
        ]
    )

    required_overlap = []
    preferred_overlap = []
    stack_overlap = []

    for technology in technologies:

        if technology in required:

            if technology not in required_overlap:
                required_overlap.append(
                    technology
                )

        if technology in preferred:

            if technology not in preferred_overlap:
                preferred_overlap.append(
                    technology
                )

        if technology in stack:

            if technology not in stack_overlap:
                stack_overlap.append(
                    technology
                )

    # --------------------------------------------------------
    # Direct technology score
    # --------------------------------------------------------

    score = 0

    score += (
        len(required_overlap)
        * 50
    )

    score += (
        len(preferred_overlap)
        * 30
    )

    score += (
        len(stack_overlap)
        * 20
    )

    # --------------------------------------------------------
    # Role relevance
    # --------------------------------------------------------

    role_score, role_reasons = (
        get_project_role_relevance(
            project,
            job,
        )
    )

    score += role_score

    # --------------------------------------------------------
    # Cap the score
    # --------------------------------------------------------

    score = min(
        score,
        100,
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    if score >= 60:

        relevance = "direct"

    elif score >= 25:

        relevance = "strong"

    elif score > 0:

        relevance = "supporting"

    else:

        relevance = "low"

    return {
        "score": score,

        "relevance": relevance,

        "required_overlap":
            sorted(
                required_overlap
            ),

        "preferred_overlap":
            sorted(
                preferred_overlap
            ),

        "technology_stack_overlap":
            sorted(
                stack_overlap
            ),

        "role_relevance":
            role_reasons,
    }


def rank_projects(
    profile,
    job,
):

    projects = profile.get(
        "projects",
        [],
    )

    if not isinstance(
        projects,
        list,
    ):
        return []

    ranked = []

    for project in projects:

        if not isinstance(
            project,
            dict,
        ):
            continue

        score_data = score_project(
            project,
            job,
        )

        matched = []

        for field in [
            "required_overlap",
            "preferred_overlap",
            "technology_stack_overlap",
        ]:

            for item in score_data[field]:

                if item not in matched:
                    matched.append(item)

        ranked.append(
            {
                "name": project.get(
                    "name",
                    "",
                ),

                "technologies": project.get(
                    "technologies",
                    [],
                ),

                "description": project.get(
                    "description",
                    "",
                ),

                "score": score_data[
                    "score"
                ],

                "relevance": score_data[
                    "relevance"
                ],

                "matched_requirements":
                    matched,

                "role_relevance":
                    score_data[
                        "role_relevance"
                    ],
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["score"],
            item["name"].lower(),
        )
    )

    return ranked


# ============================================================
# EXPERIENCE RELEVANCE
# ============================================================

def rank_experience(
    profile,
    job,
):

    experiences = profile.get(
        "experience",
        [],
    )

    if not isinstance(
        experiences,
        list,
    ):
        return []

    job_text = normalize(
        " ".join(
            str(job.get(field, ""))
            for field in [
                "position",
                "required_skills",
                "preferred_skills",
                "tech_stack",
                "responsibilities",
            ]
        )
    )

    result = []

    for experience in experiences:

        if not isinstance(
            experience,
            dict,
        ):
            continue

        responsibilities = experience.get(
            "responsibilities",
            [],
        )

        if not isinstance(
            responsibilities,
            list,
        ):
            responsibilities = []

        scored = []

        for responsibility in responsibilities:

            if not isinstance(
                responsibility,
                str,
            ):
                continue

            text = normalize(
                responsibility
            )

            score = 0

            keywords = [
                "python",
                "backend",
                "api",
                "automation",
                "testing",
                "deployment",
                "data",
                "model",
                "software",
                "script",
            ]

            for keyword in keywords:

                if (
                    keyword in text
                    and keyword in job_text
                ):

                    score += 10

            scored.append(
                (
                    score,
                    responsibility,
                )
            )

        scored.sort(
            key=lambda item: -item[0]
        )

        result.append(
            {
                "company": experience.get(
                    "company",
                    "",
                ),

                "role": experience.get(
                    "role",
                    "",
                ),

                "responsibilities": [
                    responsibility
                    for _, responsibility
                    in scored
                ],
            }
        )

    return result


# ============================================================
# CONTENT STRATEGY
# ============================================================

def build_content_strategy(
    profile,
    job,
    match_result,
):

    ranked_skills = rank_skills(
        profile,
        job,
        match_result,
    )

    ranked_projects = rank_projects(
        profile,
        job,
    )

    ranked_experience = rank_experience(
        profile,
        job,
    )

    # Top 10 skills only.
    priority_skills = [
        item["skill"]
        for item in ranked_skills[:10]
    ]

    # Keep all projects ranked.
    # The AI can choose the appropriate number.
    priority_projects = [
        project["name"]
        for project in ranked_projects
    ]

    return {
        "summary": {
            "instruction": (
                "Write a concise recruiter-focused "
                "summary using only verified candidate "
                "facts. Connect real experience and "
                "projects to the target role."
            )
        },

        "skills": {
            "prioritize": priority_skills,

            "instruction": (
                "Prioritize direct technology matches "
                "first. Then use strong supporting skills "
                "already present in the candidate profile."
            ),
        },

        "experience": {
            "prioritize": ranked_experience,

            "instruction": (
                "Prioritize responsibilities that provide "
                "the strongest evidence for the target role. "
                "Do not change their factual meaning."
            ),
        },

        "projects": {
            "prioritize": ranked_projects,

            "instruction": (
                "Prioritize projects using direct technology "
                "overlap first, strong role relevance second, "
                "and supporting relevance third. Do not "
                "exclude a useful project solely because it "
                "has no exact job-stack match."
            ),
        },

        "content_quality": {
            "short_and_specific": True,
            "avoid_generic_phrases": True,
            "avoid_repetition": True,
            "prefer_evidence_over_claims": True,
            "use_action_oriented_language": True,
            "do_not_invent_metrics": True,
            "do_not_invent_facts": True,
        },
    }


# ============================================================
# SAFETY RULES
# ============================================================

def build_tailoring_rules():

    return {
        "source_of_truth": "career_profile",

        "allow_new_facts": False,
        "allow_new_projects": False,
        "allow_new_experience": False,
        "allow_new_education": False,
        "allow_new_certifications": False,
        "allow_new_achievements": False,
        "allow_skill_invention": False,
        "allow_requirement_claims_without_evidence": False,

        "allow_factually_supported_rewriting": True,

        "changes_allowed": [
            "Reorder skills according to relevance.",
            "Deduplicate skills.",
            "Prioritize stronger existing skills.",
            "Reorder projects according to relevance.",
            "Prioritize stronger project evidence.",
            "Reorder experience responsibilities.",
            "Rewrite existing content for clarity.",
            "Rewrite existing content for conciseness.",
            "Create a concise summary from verified facts.",
            "Adjust section emphasis.",
            "Remove unnecessary repetition.",
        ],

        "changes_not_allowed": [
            "Inventing skills.",
            "Inventing projects.",
            "Inventing employment.",
            "Inventing education.",
            "Inventing certifications.",
            "Inventing achievements.",
            "Inventing metrics.",
            "Inventing percentages.",
            "Inventing users, scale, revenue, or impact.",
            "Claiming missing technologies.",
            "Claiming experience the candidate does not have.",
            "Changing dates.",
            "Changing companies.",
            "Changing institutions.",
            "Changing qualifications.",
        ],
    }


# ============================================================
# MAIN TAILORING FUNCTION
# ============================================================

def tailor_resume(
    job,
    match_result=None,
):
    """
    Public entry point.

    Loads the candidate profile automatically.
    """

    profile = load_profile()

    if match_result is None:
        match_result = {}

    rules = build_tailoring_rules()

    ranked_skills = rank_skills(
        profile,
        job,
        match_result,
    )

    ranked_projects = rank_projects(
        profile,
        job,
    )

    ranked_experience = rank_experience(
        profile,
        job,
    )

    content_strategy = build_content_strategy(
        profile,
        job,
        match_result,
    )

    groups = get_job_requirement_groups(
        job
    )

    matched_requirements = {
        "required": [],
        "preferred": [],
        "technology_stack": [],
    }

    missing_requirements = {
        "required": [],
        "preferred": [],
        "technology_stack": [],
    }

    profile_skills = get_profile_skills(
        profile
    )

    for field, output_key in [
        (
            "required_skills",
            "required",
        ),
        (
            "preferred_skills",
            "preferred",
        ),
        (
            "tech_stack",
            "technology_stack",
        ),
    ]:

        for job_skill in groups[field]:

            profile_skill = find_skill_match(
                profile_skills,
                job_skill,
            )

            if profile_skill:

                if (
                    job_skill
                    not in matched_requirements[
                        output_key
                    ]
                ):

                    matched_requirements[
                        output_key
                    ].append(
                        job_skill
                    )

            else:

                if (
                    job_skill
                    not in missing_requirements[
                        output_key
                    ]
                ):

                    missing_requirements[
                        output_key
                    ].append(
                        job_skill
                    )

    return {
        "status": "success",

        "rules": rules,

        "job_requirements": {
            "required": groups[
                "required_skills"
            ],

            "preferred": groups[
                "preferred_skills"
            ],

            "technology_stack": groups[
                "tech_stack"
            ],
        },

        "matched_requirements":
            matched_requirements,

        "missing_requirements":
            missing_requirements,

        "priority_skills":
            content_strategy[
                "skills"
            ][
                "prioritize"
            ],

        "all_ranked_skills":
            ranked_skills,

        "priority_projects":
            [
                project["name"]
                for project in ranked_projects
            ],

        "ranked_projects":
            ranked_projects,

        "priority_experience":
            ranked_experience,

        "content_strategy":
            content_strategy,
    }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def tailor_current_resume(
    job,
    match_result=None,
):

    return tailor_resume(
        job,
        match_result,
    )