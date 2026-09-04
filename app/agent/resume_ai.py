import json
import httpx

from app.agent.career_profile import load_profile
from app.agent.resume_tailor import tailor_resume


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


# ============================================================
# BASIC HELPERS
# ============================================================

def _clean_list(values):
    """
    Keep only real, non-empty strings.
    """

    if not isinstance(values, list):
        return []

    result = []

    for value in values:

        if not isinstance(value, str):
            continue

        value = value.strip()

        if value and value not in result:
            result.append(value)

    return result


def _clean_dict_list(values):
    """
    Keep only dictionary objects from a list.
    """

    if not isinstance(values, list):
        return []

    return [
        value
        for value in values
        if isinstance(value, dict)
    ]


# ============================================================
# PROFILE SNAPSHOT
# ============================================================

def _profile_snapshot(profile):
    """
    Extract the candidate's verified information.

    This information is the source of truth.
    """

    personal = profile.get(
        "personal",
        {},
    )

    links = profile.get(
        "professional_links",
        {},
    )

    return {
        "personal": {
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

        "education": profile.get(
            "education",
            [],
        ),

        "skills": profile.get(
            "skills",
            {},
        ),

        "experience": profile.get(
            "experience",
            [],
        ),

        "projects": profile.get(
            "projects",
            [],
        ),

        "certifications": profile.get(
            "certifications",
            [],
        ),

        "achievements": profile.get(
            "achievements",
            [],
        ),

        "preferred_roles": profile.get(
            "preferred_roles",
            [],
        ),

        "experience_level": profile.get(
            "experience_level",
            [],
        ),
    }


# ============================================================
# AI PROMPT
# ============================================================

def build_resume_prompt(
    profile,
    job,
    match_result,
    tailoring_plan,
):
    """
    Build a strict prompt for Qwen.

    Qwen is used for wording and summary quality,
    NOT for creating candidate facts.
    """

    snapshot = _profile_snapshot(
        profile
    )

    return f"""
You are a professional ATS-friendly resume writing assistant.

Create a concise, high-quality resume presentation for the
candidate based on the target job.

IMPORTANT:

The candidate career profile is the ONLY source of truth.

The job description controls:
- relevance
- prioritization
- wording
- section emphasis

The job description MUST NOT introduce new candidate facts.

============================================================
CANDIDATE PROFILE
============================================================

{json.dumps(
    snapshot,
    indent=2,
    ensure_ascii=False,
)}

============================================================
TARGET JOB
============================================================

{json.dumps(
    job,
    indent=2,
    ensure_ascii=False,
)}

============================================================
MATCH RESULT
============================================================

{json.dumps(
    match_result,
    indent=2,
    ensure_ascii=False,
)}

============================================================
TAILORING PLAN
============================================================

{json.dumps(
    tailoring_plan,
    indent=2,
    ensure_ascii=False,
)}

============================================================
STRICT FACTUAL RULES
============================================================

The candidate profile is the source of truth.

NEVER invent:

- companies
- job titles
- employment dates
- education institutions
- degrees
- graduation dates
- CGPA
- certifications
- achievements
- projects
- technologies
- programming languages
- databases
- cloud platforms
- metrics
- percentages
- users
- revenue
- scale
- leadership
- ownership
- production experience
- years of experience

NEVER change factual information.

NEVER replace an existing institution with another institution.

NEVER replace an existing company with another company.

NEVER change dates.

NEVER create a fake certification.

NEVER create a fake achievement.

NEVER claim a missing job technology as candidate experience.

============================================================
SUMMARY RULES
============================================================

Write a concise recruiter-focused professional summary.

The summary MUST:

- Be 2 or 3 sentences.
- Be approximately 45–75 words.
- Start with the candidate's current verified identity,
  education status, or actual experience.
- Highlight the candidate's strongest relevant skills.
- Connect those skills to the target role when the connection
  is directly supported by the profile.
- Prefer concrete technologies and actual project experience
  over generic personality statements.
- Avoid simply copying the internship responsibilities.
- Avoid listing every skill.
- Avoid generic phrases such as:
  "passionate professional",
  "results-driven individual",
  "dynamic candidate",
  "proven track record",
  "strong candidate".
- Do not add a career goal unless it is supported by the
  candidate's preferred roles or experience.
- Do not claim the candidate meets requirements that are
  missing from the profile.

Every statement must be supported by the candidate profile.

The target job should influence what is emphasized,
but MUST NOT create candidate experience.

============================================================
SKILL RULES
============================================================

Only use candidate skills.

Prioritize skills relevant to the target job.

If the job requires:

AWS
Rust
PostgreSQL
Redis
TypeScript
Terraform
SolidJS
TimescaleDB

and those skills are not in the candidate profile,

DO NOT add them to the candidate's skills.

They may appear in missing_requirements.

============================================================
PROJECT RULES
============================================================

Only use projects from the candidate profile.

Do not create projects.

Do not rename projects into fictional projects.

Do not add technologies to projects.

Do not invent project metrics.

Do not invent users.

Do not invent scale.

Do not invent business impact.

Use the tailoring plan to determine project priority.

============================================================
EXPERIENCE RULES
============================================================

The candidate's actual experience must remain unchanged.

Responsibilities may be shortened or reordered.

Their factual meaning must remain unchanged.

Do not create new responsibilities.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use this structure:

{{
    "summary": ""
}}

IMPORTANT:

Only generate the summary.

Do NOT generate education.

Do NOT generate experience.

Do NOT generate projects.

Do NOT generate certifications.

Do NOT generate achievements.

Do NOT generate skills.

Those sections will be assembled directly from the verified
candidate profile by the application.

Return no markdown.
Return no explanation.
"""
# ============================================================
# SUMMARY CLEANING
# ============================================================

def _clean_summary_text(summary):
    """
    Clean AI-generated summary formatting without changing
    its factual meaning.
    """

    if not isinstance(
        summary,
        str,
    ):
        return ""

    summary = summary.strip()

    # --------------------------------------------------------
    # Remove markdown accidentally returned by the model.
    # --------------------------------------------------------

    summary = summary.replace(
        "**",
        "",
    )

    summary = summary.replace(
        "__",
        "",
    )

    summary = summary.replace(
        "`",
        "",
    )

    # --------------------------------------------------------
    # Normalize whitespace.
    # --------------------------------------------------------

    summary = " ".join(
        summary.split()
    )

    # --------------------------------------------------------
    # Fix common token-spacing problems.
    # --------------------------------------------------------

    replacements = {
        "AComputer": "A Computer",
        "aComputer": "a Computer",
        "AnComputer": "A Computer",
        "ComputerScience": "Computer Science",
        "hands-onexperience": "hands-on experience",
        "experiencewith": "experience with",
        "workedwith": "worked with",
        "builtand": "built and",
        "developedand": "developed and",
        "usingPython": "using Python",
        "usingNode.js": "using Node.js",
        "usingFastAPI": "using FastAPI",
    }

    for old, new in replacements.items():

        summary = summary.replace(
            old,
            new,
        )

    # --------------------------------------------------------
    # Remove accidental leading punctuation.
    # --------------------------------------------------------

    summary = summary.strip(
        " \n\t.-"
    )

    return summary

# ============================================================
# AI SUMMARY GENERATION
# ============================================================

async def generate_ai_summary(
    profile,
    job,
    match_result,
    tailoring_plan,
):
    """
    Generate ONLY the professional summary.

    Qwen may improve wording and relevance,
    but it cannot introduce candidate facts.
    """

    prompt = build_resume_prompt(
        profile=profile,
        job=job,
        match_result=match_result,
        tailoring_plan=tailoring_plan,
    )

    payload = {
        "model": MODEL_NAME,

        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict factual resume writer. "

                    "The candidate profile is the ONLY source of truth. "

                    "Write a concise 2-3 sentence recruiter-focused "
                    "professional summary. "

                    "Use the target job only to decide which verified "
                    "candidate skills and experience should receive emphasis. "

                    "Never invent, infer, exaggerate, or assume candidate "
                    "experience. "

                    "Never claim expertise, seniority, leadership, ownership, "
                    "production experience, scalability experience, cloud "
                    "experience, or years of experience unless explicitly "
                    "supported by the candidate profile. "

                    "Do not simply repeat the internship responsibilities. "

                    "Prefer concrete technologies, projects, and actual "
                    "hands-on work when supported. "

                    "Avoid generic phrases such as proven track record, "
                    "results-driven, dynamic professional, passionate "
                    "professional, and strong candidate. "

                    "Return ONLY valid JSON."
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
            "temperature": 0.1,
            "num_predict": 300,
        },
    }

    try:

        async with httpx.AsyncClient(
            timeout=None
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

    except Exception as exc:

        return {
            "status": "error",
            "message": (
                f"AI summary generation failed: {exc}"
            ),
        }

    content = (
        data
        .get("message", {})
        .get("content", "")
    )

    if not content:

        return {
            "status": "error",
            "message": (
                "Qwen returned an empty summary."
            ),
        }

    try:

        generated = json.loads(
            content
        )

    except json.JSONDecodeError:

        return {
            "status": "error",
            "message": (
                "Qwen returned invalid JSON."
            ),
            "raw": content,
        }

    summary = generated.get(
        "summary",
        "",
    )

    if not isinstance(
        summary,
        str,
    ):
        summary = ""

    summary = _clean_summary_text(
        summary
    )

    if not summary:

        return {
            "status": "error",
            "message": (
                "Qwen did not generate a resume summary."
            ),
        }

    return {
        "status": "success",
        "summary": summary,
    }


# ============================================================
# PROJECT SELECTION
# ============================================================

def _select_projects(
    profile,
    tailoring_plan,
    limit=3,
):
    """
    Select ONLY real projects from the profile.

    Ordering comes from resume_tailor.py.
    """

    projects = profile.get(
        "projects",
        [],
    )

    if not isinstance(
        projects,
        list,
    ):
        return []

    ranked = tailoring_plan.get(
        "ranked_projects",
        [],
    )

    project_map = {}

    for project in projects:

        if not isinstance(
            project,
            dict,
        ):
            continue

        name = project.get(
            "name",
            "",
        )

        if name:
            project_map[
                name
            ] = project

    selected = []

    for ranked_project in ranked:

        if not isinstance(
            ranked_project,
            dict,
        ):
            continue

        name = ranked_project.get(
            "name",
            "",
        )

        if name in project_map:

            selected.append(
                project_map[name]
            )

        if len(selected) >= limit:
            break

    # Safety fallback.
    if not selected:

        selected = projects[:limit]

    return selected


# ============================================================
# SKILL SELECTION
# ============================================================

def _select_skills(
    profile,
    tailoring_plan,
    limit=15,
):
    """
    Select skills ONLY from the verified career profile.

    Rules:

    1. A skill must already exist in career_profile.json.
    2. The job cannot introduce a new skill.
    3. Tailoring can change priority, not factual content.
    4. No keyword-based skill invention.
    5. Duplicate skills are removed.
    """

    skill_groups = profile.get(
        "skills",
        {},
    )

    if not isinstance(
        skill_groups,
        dict,
    ):
        return []

    # --------------------------------------------------------
    # Collect verified profile skills
    # --------------------------------------------------------

    profile_skills = []

    for values in skill_groups.values():

        if not isinstance(
            values,
            list,
        ):
            continue

        for skill in values:

            if not isinstance(
                skill,
                str,
            ):
                continue

            skill = skill.strip()

            if not skill:
                continue

            # Exact profile fact only.
            if skill not in profile_skills:

                profile_skills.append(
                    skill
                )

    if not profile_skills:
        return []

    # --------------------------------------------------------
    # Tailoring priority
    # --------------------------------------------------------

    priority = tailoring_plan.get(
        "priority_skills",
        [],
    )

    if not isinstance(
        priority,
        list,
    ):
        priority = []

    selected = []

    # --------------------------------------------------------
    # 1. Select only exact profile matches
    #    from tailoring priorities.
    # --------------------------------------------------------

    for priority_skill in priority:

        if not isinstance(
            priority_skill,
            str,
        ):
            continue

        priority_skill = (
            priority_skill
            .strip()
            .lower()
        )

        if not priority_skill:
            continue

        for profile_skill in profile_skills:

            if (
                profile_skill.lower()
                == priority_skill
            ):

                if (
                    profile_skill
                    not in selected
                ):

                    selected.append(
                        profile_skill
                    )

                break

        if len(selected) >= limit:
            return selected[:limit]

    # --------------------------------------------------------
    # 2. Fill remaining space with profile skills.
    #
    # This is still completely grounded.
    #
    # No keyword inference.
    # No AI-generated technologies.
    # --------------------------------------------------------

    for profile_skill in profile_skills:

        if len(selected) >= limit:
            break

        if profile_skill in selected:
            continue

        selected.append(
            profile_skill
        )

    return selected[:limit]

    # --------------------------------------------------------
    # Collect all verified profile skills
    # --------------------------------------------------------

    for values in skill_groups.values():

        if not isinstance(
            values,
            list,
        ):
            continue

        for skill in values:

            if not isinstance(
                skill,
                str,
            ):
                continue

            skill = skill.strip()

            if (
                skill
                and skill not in profile_skills
            ):
                profile_skills.append(
                    skill
                )

    # --------------------------------------------------------
    # Candidate role relevance
    # --------------------------------------------------------

    preferred_roles = profile.get(
        "preferred_roles",
        [],
    )

    if not isinstance(
        preferred_roles,
        list,
    ):
        preferred_roles = []

    role_text = " ".join(
        str(role)
        for role in preferred_roles
    ).lower()

    # --------------------------------------------------------
    # Tailored priority skills
    # --------------------------------------------------------

    priority = tailoring_plan.get(
        "priority_skills",
        [],
    )

    if not isinstance(
        priority,
        list,
    ):
        priority = []

    selected = []

    # --------------------------------------------------------
    # 1. Explicitly matched / prioritized skills
    # --------------------------------------------------------

    for skill in priority:

        for profile_skill in profile_skills:

            if (
                profile_skill.lower()
                == str(skill).lower()
            ):

                if (
                    profile_skill
                    not in selected
                ):

                    selected.append(
                        profile_skill
                    )

                break

    # --------------------------------------------------------
    # 2. Strong software/backend/AI skills
    #
    # These are preferred over generic languages when the
    # target job does not explicitly match them.
    # --------------------------------------------------------

    high_value_keywords = [
        "python",
        "fastapi",
        "node.js",
        "javascript",
        "typescript",
        "rest",
        "api",
        "react",
        "mongodb",
        "mysql",
        "postgresql",
        "git",
        "github",
        "linux",
        "bash",
        "llm",
        "openai",
        "machine learning",
        "scikit-learn",
        "computer vision",
        "solidity",
        "ethereum",
    ]

    for keyword in high_value_keywords:

        for profile_skill in profile_skills:

            skill_lower = (
                profile_skill.lower()
            )

            if (
                keyword in skill_lower
                or skill_lower in keyword
            ):

                if (
                    profile_skill
                    not in selected
                ):

                    selected.append(
                        profile_skill
                    )

    # --------------------------------------------------------
    # 3. Remaining skills only if we still need them.
    #
    # Avoid filling the resume with every programming
    # language from the profile.
    # --------------------------------------------------------

    generic_language_skills = {
        "c",
        "c++",
        "java",
        "html",
        "css",
    }

    for skill in profile_skills:

        if len(selected) >= limit:
            break

        if skill in selected:
            continue

        if (
            skill.lower()
            in generic_language_skills
        ):
            continue

        selected.append(
            skill
        )

    # --------------------------------------------------------
    # 4. Add generic languages only if there is still space.
    # --------------------------------------------------------

    for skill in profile_skills:

        if len(selected) >= limit:
            break

        if skill in selected:
            continue

        selected.append(
            skill
        )

    return selected[:limit]

# ============================================================
# BUILD FINAL GROUNDED RESUME
# ============================================================

def _build_grounded_resume(
    profile,
    job,
    tailoring_plan,
    summary,
):
    """
    Assemble the final resume.

    IMPORTANT:

    Factual sections are copied from the profile.

    AI does NOT control these sections.
    """

    personal = profile.get(
        "personal",
        {},
    )

    links = profile.get(
        "professional_links",
        {},
    )

    # --------------------------------------------------------
    # VERIFIED FACTUAL SECTIONS
    # --------------------------------------------------------

    education = _clean_dict_list(
        profile.get(
            "education",
            [],
        )
    )

    experience = _clean_dict_list(
        profile.get(
            "experience",
            [],
        )
    )

    certifications = _clean_list(
        profile.get(
            "certifications",
            [],
        )
    )

    achievements = _clean_list(
        profile.get(
            "achievements",
            [],
        )
    )

    # --------------------------------------------------------
    # Tailored but profile-grounded sections
    # --------------------------------------------------------

    skills = _select_skills(
        profile,
        tailoring_plan,
    )

    projects = _select_projects(
        profile,
        tailoring_plan,
    )

    # --------------------------------------------------------
    # Missing requirements
    # --------------------------------------------------------

    missing = tailoring_plan.get(
        "missing_requirements",
        {},
    )

    missing_requirements = []

    if isinstance(
        missing,
        dict,
    ):

        for values in missing.values():

            if not isinstance(
                values,
                list,
            ):
                continue

            for value in values:

                if (
                    isinstance(
                        value,
                        str,
                    )
                    and value.strip()
                ):

                    if (
                        value
                        not in missing_requirements
                    ):

                        missing_requirements.append(
                            value
                        )

    # --------------------------------------------------------
    # Final resume
    # --------------------------------------------------------

    return {
        "target": {
            "company": job.get(
                "company",
                "",
            ),

            "position": job.get(
                "position",
                "",
            ),

            "source_url": job.get(
                "application_url",
                "",
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

        "summary": summary,

        "skills": skills,

        "experience": experience,

        "projects": projects,

        "education": education,

        "certifications": certifications,

        "achievements": achievements,

        "missing_requirements":
            missing_requirements,

        "grounding": {
            "source": "career_profile",

            "facts_created_by_ai": False,

            "ai_generated_fields": [
                "summary",
            ],

            "profile_controlled_fields": [
                "candidate",
                "professional_links",
                "skills",
                "experience",
                "projects",
                "education",
                "certifications",
                "achievements",
            ],
        },
    }


# ============================================================
# MAIN AI RESUME FUNCTION
# ============================================================

async def create_ai_resume(
    job,
    match_result,
):
    """
    Main entry point used by test_resume_validator.py.

    Pipeline:

        career profile
              ↓
        resume tailoring
              ↓
        Qwen summary
              ↓
        profile-grounded assembly
              ↓
        validator
    """

    try:

        profile = load_profile()

        # ----------------------------------------------------
        # Tailoring
        # ----------------------------------------------------

        tailoring_result = tailor_resume(
            job,
            match_result,
        )

        if (
            not isinstance(
                tailoring_result,
                dict,
            )
            or tailoring_result.get(
                "status"
            ) != "success"
        ):

            return {
                "status": "error",
                "message": (
                    "Resume tailoring failed."
                ),
            }

        # ----------------------------------------------------
        # Generate ONLY summary with AI
        # ----------------------------------------------------

        summary_result = await generate_ai_summary(
            profile=profile,
            job=job,
            match_result=match_result,
            tailoring_plan=tailoring_result,
        )

        if (
            summary_result.get(
                "status"
            ) != "success"
        ):

            return summary_result

        # ----------------------------------------------------
        # Assemble resume from verified data
        # ----------------------------------------------------

        resume = _build_grounded_resume(
            profile=profile,
            job=job,
            tailoring_plan=tailoring_result,
            summary=summary_result[
                "summary"
            ],
        )

        return {
            "status": "success",
            "resume": resume,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": (
                f"AI resume generation failed: {exc}"
            ),
        }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

async def generate_ai_resume(
    profile,
    job,
    match_result,
    tailoring_plan=None,
):
    """
    Compatibility wrapper.

    Some earlier code may call generate_ai_resume().
    """

    if tailoring_plan is None:

        tailoring_plan = tailor_resume(
            job,
            match_result,
        )

    summary_result = await generate_ai_summary(
        profile=profile,
        job=job,
        match_result=match_result,
        tailoring_plan=tailoring_plan,
    )

    if (
        summary_result.get(
            "status"
        ) != "success"
    ):

        return summary_result

    resume = _build_grounded_resume(
        profile=profile,
        job=job,
        tailoring_plan=tailoring_plan,
        summary=summary_result[
            "summary"
        ],
    )

    return {
        "status": "success",
        "resume": resume,
    }