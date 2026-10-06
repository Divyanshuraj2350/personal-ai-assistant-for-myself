import json
import httpx


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"

# Keep the prompt small enough for Qwen3:8b on a laptop.
MAX_ANALYSIS_CONTENT = 4500

# Maximum number of generated tokens.
# The requested JSON is relatively small.
MAX_OUTPUT_TOKENS = 2048


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


def _clean_analysis_value(value, expected_type):
    """
    Normalize one field returned by Qwen.
    """

    if expected_type == "list":

        if not isinstance(value, list):
            return []

        cleaned = []

        for item in value:

            if item is None:
                continue

            text = str(item).strip()

            if text:
                cleaned.append(text)

        return cleaned

    if value is None:
        return None

    if isinstance(value, str):

        value = value.strip()

        return value or None

    return str(value)


def _normalize_analysis(analysis, source_url):
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

    if not isinstance(analysis, dict):
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

    # Never lose the original source URL.
    if not result["application_url"]:
        result["application_url"] = source_url

    return result


def _has_meaningful_job_information(result):
    """
    Prevent empty/meaningless Qwen responses from being
    treated as successful analyses.
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

        if isinstance(value, list):

            if value:
                non_empty += 1

        elif value:

            non_empty += 1

    return non_empty >= 2


def _parse_json_response(text):
    """
    Safely parse JSON returned by Ollama.
    """

    if not text:
        return None

    text = text.strip()

    # Remove accidental markdown fences.
    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        # Try to recover the first JSON object.
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return None

        try:

            return json.loads(
                text[start:end + 1]
            )

        except json.JSONDecodeError:

            return None


async def call_qwen(prompt):
    """
    Send one prompt to local Qwen through Ollama.

    Important:
    - thinking disabled
    - JSON mode enabled
    - output token count limited
    """

    payload = {
        "model": MODEL_NAME,

        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract structured job information. "
                    "Use only the supplied job posting. "
                    "Never invent missing information."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        "stream": False,

        # Important for Qwen3.
        "think": False,

        # Ask Ollama for JSON.
        "format": "json",

        "options": {
            "temperature": 0,
            "num_predict": MAX_OUTPUT_TOKENS,
        },
    }

    try:

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=90.0,
                write=30.0,
                pool=30.0,
            )
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

    except httpx.TimeoutException as exc:

        raise RuntimeError(
            "Qwen HTTP request timed out."
        ) from exc

    except Exception as exc:

        raise RuntimeError(
            f"Could not contact Qwen: {exc}"
        ) from exc

    message = data.get(
        "message",
        {},
    )

    content = message.get(
        "content",
        "",
    )

    if not content:

        raise RuntimeError(
            "Qwen returned an empty response."
        )

    
    parsed = _parse_json_response(content)

    if parsed is None:
        print("\n[DEBUG] Qwen raw response:")
        print(repr(content))
        print("\n[DEBUG] End of Qwen response\n")

        raise RuntimeError(
            "Qwen returned invalid JSON."
        )


    return parsed


async def analyze_job(job_data):
    """
    Analyze a fetched job page using local Qwen3:8b.

    The model receives a shortened version of the job
    content to avoid very slow inference on a laptop.
    """

    if not job_data:

        return {
            "status": "error",
            "error": "No job data provided.",
        }

    if job_data.get("status") != "success":

        return {
            "status": "error",
            "error": job_data.get(
                "error",
                "Could not read the job page.",
            ),
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
                "The job page contains no readable content."
            ),
        }

    content = str(content).strip()

    if len(content) < 100:

        return {
            "status": "error",
            "error": (
                "The job page does not contain enough "
                "job-description content."
            ),
        }

    # ------------------------------------------------------
    # IMPORTANT:
    # Reduce the amount of text sent to Qwen.
    # ------------------------------------------------------

    original_length = len(content)

    if len(content) > MAX_ANALYSIS_CONTENT:

        content = (
            content[:MAX_ANALYSIS_CONTENT]
            + "\n[JOB CONTENT TRUNCATED]"
        )

    print(
        f"[JOB ANALYZER] Original content: "
        f"{original_length} chars"
    )

    print(
        f"[JOB ANALYZER] Qwen content: "
        f"{len(content)} chars"
    )

    # ------------------------------------------------------
    # Small structured prompt.
    # ------------------------------------------------------

    prompt = f"""
Extract structured information from this job posting.

RULES:
1. Use ONLY the supplied text.
2. Do NOT invent missing information.
3. If information is missing, use null or [].
4. Return ONLY valid JSON.
5. Keep lists short and factual.
6. Do not write explanations outside the JSON.

Return exactly this structure:

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

JOB TITLE:
{title}

JOB URL:
{url}

JOB CONTENT:
{content}
"""

    print(
        f"[JOB ANALYZER] Prompt length: "
        f"{len(prompt)} chars"
    )

    print(
        f"[JOB ANALYZER] Sending request to "
        f"{MODEL_NAME}..."
    )

    try:

        analysis = await call_qwen(
            prompt
        )

    except Exception as exc:

        print(
            f"[JOB ANALYZER] Qwen error: {exc}"
        )

        return {
            "status": "error",
            "error": str(exc),
        }

    print(
        "[JOB ANALYZER] Qwen analysis completed."
    )

    normalized = _normalize_analysis(
        analysis,
        url,
    )

    if not _has_meaningful_job_information(
        normalized
    ):

        return {
            "status": "error",
            "error": (
                "Qwen returned insufficient "
                "job information."
            ),
        }

    return {
        "status": "success",
        "job": normalized,
        "source_url": url,
    }