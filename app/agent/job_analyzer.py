import json

import httpx


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


def _empty_result():
    return {
        "company": None,
        "position": None,
        "location": None,
        "work_mode": None,
        "experience": [],
        "education": [],
        "required_skills": [],
        "preferred_skills": [],
        "responsibilities": [],
        "tech_stack": [],
        "salary": None,
        "visa_sponsorship": None,
        "application_url": None,
    }


def _clean_analysis_value(
    value,
    expected_type,
):
    """
    Keep analyzer output predictable.

    Lists must remain lists.
    Scalar fields may be None or strings.
    """

    if expected_type == "list":

        if not isinstance(
            value,
            list,
        ):
            return []

        return [
            str(item).strip()
            for item in value
            if item is not None
            and str(item).strip()
        ]

    if value is None:
        return None

    if isinstance(
        value,
        str,
    ):

        value = value.strip()

        return value or None

    return str(value)


def _normalize_analysis(
    analysis,
    source_url,
):
    """
    Normalize Qwen output into the application's
    expected job schema.
    """

    result = _empty_result()

    list_fields = {
        "experience",
        "education",
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "tech_stack",
    }

    scalar_fields = {
        "company",
        "position",
        "location",
        "work_mode",
        "salary",
        "visa_sponsorship",
        "application_url",
    }

    if not isinstance(
        analysis,
        dict,
    ):

        return result

    for field in list_fields:

        result[field] = _clean_analysis_value(
            analysis.get(field),
            "list",
        )

    for field in scalar_fields:

        result[field] = _clean_analysis_value(
            analysis.get(field),
            "scalar",
        )

    # Always preserve the original URL if the model
    # failed to return an application URL.

    if not result["application_url"]:

        result[
            "application_url"
        ] = source_url

    return result


def _has_meaningful_job_information(
    result
):
    """
    Prevent an apparently successful analysis
    when Qwen returned almost no job information.
    """

    important_fields = [
        result.get("company"),
        result.get("position"),
        result.get("location"),
        result.get("work_mode"),
        result.get("experience"),
        result.get("education"),
        result.get("required_skills"),
        result.get("preferred_skills"),
        result.get("responsibilities"),
        result.get("tech_stack"),
        result.get("salary"),
    ]

    non_empty = 0

    for value in important_fields:

        if isinstance(
            value,
            list,
        ):

            if value:
                non_empty += 1

        elif value:

            non_empty += 1

    # Company + position alone is not enough.

    if non_empty < 2:
        return False

    return True


async def analyze_job(job_data):
    """
    Analyze a fetched job page with Qwen.

    The analyzer never invents missing information.
    """

    if not job_data:

        return {
            "status": "error",
            "error": "No job data provided.",
        }

    job_status = job_data.get(
        "status"
    )

    if job_status != "success":

        return {
            "status": "error",
            "error": job_data.get(
                "error",
                "Could not read the job page.",
            ),
            "fetch_status": job_status,
        }

    url = job_data.get(
        "url",
        "",
    )

    title = job_data.get(
        "title",
        "",
    )

    content = job_data.get(
        "content",
        "",
    )

    if not content:

        return {
            "status": "error",
            "error": (
                "The job page contains no readable "
                "content."
            ),
        }

    # ------------------------------------------------------
    # Protect against pages that only say "Loading..."
    # ------------------------------------------------------

    normalized_content = (
        str(content)
        .strip()
        .lower()
    )

    if (
        normalized_content == "loading..."
        or len(normalized_content) < 100
    ):

        return {
            "status": "error",
            "error": (
                "The page does not contain enough "
                "job-description content. "
                "Provide the actual job description "
                "URL if this is an application page."
            ),
        }

    prompt = f"""
Analyze the following job posting.

JOB PAGE URL:
{url}

PAGE TITLE:
{title}

JOB PAGE CONTENT:
{content}

Extract only information that is actually supported
by the job posting.

Do NOT guess or invent information.

Return ONLY valid JSON in exactly this structure:

{{
    "company": null,
    "position": null,
    "location": null,
    "work_mode": null,
    "experience": [],
    "education": [],
    "required_skills": [],
    "preferred_skills": [],
    "responsibilities": [],
    "tech_stack": [],
    "salary": null,
    "visa_sponsorship": null,
    "application_url": null
}}

Rules:

1. company:
   Extract the company name.

2. position:
   Extract the exact job title.

3. location:
   Extract the stated job location.
   If not stated, return null.

4. work_mode:
   Extract remote, hybrid, onsite, or another
   explicitly stated work arrangement.
   If not stated, return null.

5. experience:
   Include explicit experience requirements.

6. education:
   Include explicit education requirements.

7. required_skills:
   Include skills explicitly required by the role.

8. preferred_skills:
   Include skills described as preferred,
   helpful, nice-to-have, or advantageous.

9. responsibilities:
   Extract the main responsibilities.

10. tech_stack:
    Extract named technologies, programming languages,
    frameworks, databases, cloud platforms,
    infrastructure tools, and similar technologies.

11. salary:
    Extract the stated salary or salary range.

12. visa_sponsorship:
    Extract only explicit visa sponsorship information.

13. application_url:
    Use the supplied URL if it is the job/application page.

IMPORTANT:

- Never infer a technology merely because it is common
  for the role.
- Never invent experience requirements.
- Never invent education requirements.
- Never convert a missing value into a guess.
- Use [] for missing list fields.
- Use null for missing scalar fields.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a job description analysis assistant. "
                    "Extract structured information accurately. "
                    "Never invent missing information. "
                    "Return only valid JSON."
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
            "error": (
                f"Job analysis failed: {exc}"
            ),
        }

    model_content = (
        data.get(
            "message",
            {}
        ).get(
            "content",
            "",
        )
    )

    if not model_content:

        return {
            "status": "error",
            "error": (
                "Qwen returned an empty analysis."
            ),
        }

    try:

        analysis = json.loads(
            model_content
        )

    except json.JSONDecodeError:

        return {
            "status": "error",
            "error": (
                "Qwen returned invalid JSON."
            ),
            "raw": model_content,
        }

    result = _normalize_analysis(
        analysis,
        url,
    )

    if not _has_meaningful_job_information(
        result
    ):

        return {
            "status": "error",
            "error": (
                "The page did not contain enough "
                "job information to build a reliable "
                "analysis. The URL may be an application "
                "page rather than the actual job description."
            ),
            "job": result,
        }

    return {
        "status": "success",
        "source_url": url,
        "job": result,
    }