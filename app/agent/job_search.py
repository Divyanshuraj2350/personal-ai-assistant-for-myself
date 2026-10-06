import re
from urllib.parse import urlparse

from app.agent.web_tool import web_search
from app.agent.career_profile import load_profile


DEFAULT_LIMIT = 10
MAX_SEARCH_RESULTS = 100


# ==========================================================
# ROLE EXTRACTION
# ==========================================================

def extract_job_role(message):
    """
    Extract the requested job role/domain from the user's message.

    Supports:
        ML jobs
        latest ML jobs
        machine learning jobs
        AI jobs
        latest AI/ML jobs
        Python internships
        Python developer jobs
        search for Python jobs
        find me backend jobs
        show me Data Scientist openings
        remote ML jobs
        ML jobs in Bangalore
    """

    text = message.strip()

    if not text:
        return ""

    original = text
    text = re.sub(r"\s+", " ", text).strip()

    # ------------------------------------------------------
    # Normalize common abbreviations
    # ------------------------------------------------------

    normalized = text.lower()

    # ------------------------------------------------------
    # Remove common time/request words
    # ------------------------------------------------------

    normalized = re.sub(
        r"\b(?:latest|recent|new|current|available|"
        r"open|opening|openings|now|today|"
        r"currently|active)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------------------
    # Remove search-command prefixes
    # ------------------------------------------------------

    normalized = re.sub(
        r"^\s*(?:please\s+)?"
        r"(?:find|search|look\s+for|show|list|get|give\s+me|"
        r"fetch|discover|find\s+me|search\s+for)"
        r"\s*(?:me\s+)?",
        "",
        normalized,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------------------
    # Remove common job wording
    # ------------------------------------------------------

    normalized = re.sub(
        r"\b(?:job|jobs|opening|openings|position|positions|"
        r"vacancy|vacancies|opportunities|opportunity)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------------------
    # Remove internship wording, but preserve the role.
    #
    # Example:
    #   "Python internships"
    # becomes:
    #   "python"
    # ------------------------------------------------------

    normalized = re.sub(
        r"\b(?:internship|internships|intern|interns)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------------------
    # Remove location/request qualifiers.
    # ------------------------------------------------------

    normalized = re.sub(
        r"\b(?:remote|onsite|on-site|hybrid)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )

    # Remove common location expressions.
    normalized = re.sub(
        r"\b(?:in|near|around|at)\s+"
        r"[a-zA-Z][a-zA-Z .,-]{1,40}"
        r"(?=\s*$)",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )

    # ------------------------------------------------------
    # Clean punctuation
    # ------------------------------------------------------

    normalized = re.sub(
        r"[^a-zA-Z0-9+#./ -]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    # ------------------------------------------------------
    # Known role/domain aliases
    #
    # IMPORTANT:
    # Check multi-word roles before short aliases.
    # ------------------------------------------------------

    role_aliases = [
        (
            r"\b(?:artificial intelligence|ai)\s*(?:/|\band\b)?\s*"
            r"(?:machine learning|ml)\b",
            "AI/ML",
        ),
        (
            r"\b(?:machine learning|ml)\b",
            "machine learning",
        ),
        (
            r"\b(?:artificial intelligence|ai)\b",
            "artificial intelligence",
        ),
        (
            r"\b(?:data scientist|data science)\b",
            "data science",
        ),
        (
            r"\b(?:data engineer|data engineering)\b",
            "data engineering",
        ),
        (
            r"\b(?:software engineer|software engineering)\b",
            "software engineering",
        ),
        (
            r"\b(?:backend|back end)\b",
            "backend",
        ),
        (
            r"\b(?:frontend|front end)\b",
            "frontend",
        ),
        (
            r"\b(?:full stack|fullstack)\b",
            "full stack",
        ),
        (
            r"\b(?:devops|dev ops)\b",
            "DevOps",
        ),
        (
            r"\b(?:cloud engineer|cloud computing|cloud)\b",
            "cloud",
        ),
        (
            r"\b(?:cyber security|cybersecurity)\b",
            "cybersecurity",
        ),
        (
            r"\b(?:web developer|web development)\b",
            "web development",
        ),
        (
            r"\b(?:mobile developer|mobile development|android|ios)\b",
            "mobile development",
        ),
        (
            r"\b(?:python)\b",
            "Python",
        ),
        (
            r"\b(?:java)\b",
            "Java",
        ),
        (
            r"\b(?:javascript|js)\b",
            "JavaScript",
        ),
        (
            r"\b(?:react|reactjs)\b",
            "React",
        ),
        (
            r"\b(?:node|nodejs)\b",
            "Node.js",
        ),
        (
            r"\b(?:c\+\+|cpp)\b",
            "C++",
        ),
        (
            r"\b(?:sql)\b",
            "SQL",
        ),
        (
            r"\b(?:qa|quality assurance|tester|testing)\b",
            "QA",
        ),
        (
            r"\b(?:devops)\b",
            "DevOps",
        ),
    ]

    # ------------------------------------------------------
    # Find the best known role.
    # ------------------------------------------------------

    for pattern, role in role_aliases:

        if re.search(
            pattern,
            normalized,
            re.IGNORECASE,
        ):
            return role

    # ------------------------------------------------------
    # Generic fallback
    #
    # If the request contains something like:
    #
    #   "search for blockchain jobs"
    #
    # return:
    #
    #   "blockchain"
    # ------------------------------------------------------

    fallback = normalized.strip()

    # Remove trailing location/request fragments.
    fallback = re.sub(
        r"\b(?:for|in|near|around|at)\s*$",
        "",
        fallback,
        flags=re.IGNORECASE,
    )

    fallback = re.sub(
        r"\s+",
        " ",
        fallback,
    ).strip()

    if fallback:
        return fallback

    return ""


# ==========================================================
# LOCATION / REMOTE PREFERENCE
# ==========================================================

def extract_location_preferences(message):
    """
    Extract remote and location preferences.
    """

    text = message.lower()

    remote = bool(
        re.search(
            r"\bremote\b",
            text,
        )
    )

    location = ""

    match = re.search(
        r"\bin\s+([a-zA-Z][a-zA-Z .'-]{1,50})",
        message,
        re.IGNORECASE,
    )

    if match:

        location = match.group(1).strip()

        location = re.split(
            r"\b(?:related|matching|with|for)\b",
            location,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

    return {
        "remote": remote,
        "location": location,
    }


# ==========================================================
# PROFILE SKILLS
# ==========================================================

def extract_profile_skills(profile):
    """
    Extract skills from the existing career profile.
    """

    skills = []

    skill_data = profile.get(
        "skills",
        {},
    )

    if not isinstance(
        skill_data,
        dict,
    ):
        return skills

    for values in skill_data.values():

        if not isinstance(
            values,
            list,
        ):
            continue

        for value in values:

            value = str(
                value
            ).strip()

            if value and value not in skills:

                skills.append(
                    value
                )

    return skills


# ==========================================================
# ROLE-RELEVANT SKILLS
# ==========================================================

def select_relevant_skills(
    role,
    profile_skills,
    max_skills=6,
):
    """
    Select skills that are reasonably related to the
    requested role.

    This avoids putting the user's entire skill list into
    every search query.
    """

    role_text = role.lower()

    role_groups = {
        "data scientist": [
            "python",
            "machine learning",
            "ml",
            "data science",
            "pandas",
            "numpy",
            "scikit-learn",
            "statistics",
            "sql",
            "tensorflow",
            "pytorch",
        ],

        "machine learning": [
            "python",
            "machine learning",
            "ml",
            "pytorch",
            "tensorflow",
            "scikit-learn",
            "numpy",
            "pandas",
            "deep learning",
        ],

        "software engineer": [
            "python",
            "java",
            "c++",
            "javascript",
            "fastapi",
            "node.js",
            "react.js",
            "sql",
        ],

        "backend": [
            "python",
            "java",
            "c++",
            "fastapi",
            "node.js",
            "sql",
            "api",
        ],

        "frontend": [
            "javascript",
            "react.js",
            "html",
            "css",
        ],

        "web developer": [
            "javascript",
            "react.js",
            "html",
            "css",
            "node.js",
        ],
    }

    relevant_keywords = []

    for group_name, keywords in role_groups.items():

        if group_name in role_text:

            relevant_keywords.extend(
                keywords
            )

    if not relevant_keywords:
        return profile_skills[
            :max_skills
        ]

    selected = []

    for skill in profile_skills:

        normalized_skill = (
            skill.lower()
        )

        for keyword in relevant_keywords:

            if (
                keyword in normalized_skill
                or normalized_skill in keyword
            ):

                if skill not in selected:

                    selected.append(
                        skill
                    )

                break

        if len(selected) >= max_skills:
            break

    return selected


# ==========================================================
# SEARCH QUERY BUILDING
# ==========================================================

def build_search_queries(
    role,
    preferences,
    profile_skills,
):
    """
    Build targeted queries designed to discover individual job
    postings rather than generic job-board pages.

    For broad domains such as Machine Learning, use common hiring
    titles as additional search variants so a request like
    "find me job of ML domain" can reach real vacancies.
    """

    queries = []

    remote_text = (
        "remote"
        if preferences["remote"]
        else ""
    )

    location_text = (
        preferences["location"]
        if preferences["location"]
        else ""
    )

    base_parts = [role]

    if remote_text:
        base_parts.append(remote_text)

    if location_text:
        base_parts.append(location_text)

    base = " ".join(base_parts)

    # ------------------------------------------------------
    # Query 1: direct hiring search.
    # ------------------------------------------------------

    queries.append(
        base + " hiring"
    )

    # ------------------------------------------------------
    # Query 2: force individual vacancy language.
    # ------------------------------------------------------

    queries.append(
        base
        + ' "job description" "responsibilities" "requirements"'
    )

    # ------------------------------------------------------
    # Query 3: application-page signals.
    # ------------------------------------------------------

    queries.append(
        base
        + ' "apply now" "qualifications"'
    )

    # ------------------------------------------------------
    # Query 4: role-specific hiring titles.
    # ------------------------------------------------------

    role_lower = role.lower().strip()

    if role_lower in {
        "machine learning",
        "ai/ml",
        "ai ml",
    }:
        queries.append(
            "Machine Learning Engineer"
            + (" remote" if preferences["remote"] else "")
            + (f" {location_text}" if location_text else "")
            + ' "apply now"'
        )

        queries.append(
            "ML Engineer"
            + (" remote" if preferences["remote"] else "")
            + (f" {location_text}" if location_text else "")
            + ' "job description"'
        )

        # Search common ATS/job-posting URL families. These queries are
        # discovery hints only; the verifier is still the final authority.
        for site in (
            "greenhouse.io",
            "lever.co",
            "ashbyhq.com",
            "myworkdayjobs.com",
            "smartrecruiters.com",
            "jobvite.com",
            "icims.com",
            "workable.com",
        ):
            queries.append(
                f"site:{site} Machine Learning Engineer"
                + (" remote" if preferences["remote"] else "")
                + (f" {location_text}" if location_text else "")
            )

    # ------------------------------------------------------
    # Query 5: use role-relevant profile skills.
    # ------------------------------------------------------

    if profile_skills:
        skills_text = " ".join(
            profile_skills
        )

        queries.append(
            base
            + " "
            + skills_text
            + ' "job description"'
        )

    return queries


# ==========================================================
# URL VALIDATION
# ==========================================================

def is_valid_job_url(url):
    """
    Basic URL validation.

    This does not claim that the URL is a verified job.
    """

    if not url:
        return False

    try:

        parsed = urlparse(
            url
        )

    except Exception:

        return False

    return (
        parsed.scheme in {
            "http",
            "https",
        }
        and bool(
            parsed.netloc
        )
    )


# ==========================================================
# SEARCH RESULT FILTER
# ==========================================================

def looks_like_job_result(result):
    """
    Keep plausible job-related search results.

    We deliberately do NOT require the URL itself to contain
    the word 'job', because company career pages and ATS
    systems may use completely different URL structures.
    """

    if not isinstance(
        result,
        dict,
    ):
        return False

    title = str(
        result.get(
            "title",
            "",
        )
    ).lower()

    content = str(
        result.get(
            "content",
            "",
        )
    ).lower()

    url = str(
        result.get(
            "url",
            "",
        )
    )

    combined = (
        title
        + " "
        + content
        + " "
        + url.lower()
    )

    if not is_valid_job_url(
        url
    ):
        return False

    positive_terms = [
        "job",
        "jobs",
        "career",
        "careers",
        "hiring",
        "apply",
        "position",
        "role",
        "opening",
        "vacancy",
        "responsibilities",
        "qualifications",
        "requirements",
    ]

    positive_count = sum(
        1
        for term in positive_terms
        if term in combined
    )

    return positive_count >= 1


# ==========================================================
# URL QUALITY SCORING
# ==========================================================

def score_search_result(result):
    """
    Rank search results by how likely they are to be
    actual individual job postings.

    Higher score = stronger candidate.
    """

    title = str(
        result.get(
            "title",
            "",
        )
    ).lower()

    content = str(
        result.get(
            "content",
            "",
        )
    ).lower()

    url = str(
        result.get(
            "url",
            "",
        )
    ).lower()

    score = 0

    # ------------------------------------------------------
    # STRONG POSITIVE:
    # URL looks like an individual job page.
    # ------------------------------------------------------

    strong_url_patterns = [
        "/jobs/",
        "/job/",
        "/careers/",
        "/career/",
        "/positions/",
        "/position/",
        "/vacancy/",
        "/opening/",
    ]

    for pattern in strong_url_patterns:

        if pattern in url:
            score += 8

    # ------------------------------------------------------
    # ATS platforms.
    # ------------------------------------------------------

    ats_patterns = [
        "greenhouse",
        "lever.co",
        "ashbyhq",
        "myworkdayjobs",
        "smartrecruiters",
        "jobvite",
        "icims",
        "workable",
    ]

    for pattern in ats_patterns:

        if pattern in url:
            score += 8

    # ------------------------------------------------------
    # STRONG INDIVIDUAL JOB TITLE SIGNALS.
    # ------------------------------------------------------

    if (
        "data scientist" in title
        or "machine learning" in title
        or "software engineer" in title
        or "data engineer" in title
        or "ml engineer" in title
    ):
        score += 5

    # ------------------------------------------------------
    # Actual employment information.
    # ------------------------------------------------------

    job_terms = [
        "apply now",
        "employment type",
        "full-time",
        "part-time",
        "years of experience",
        "qualifications",
        "responsibilities",
        "job location",
    ]

    for term in job_terms:

        if term in content:
            score += 1

    # ------------------------------------------------------
    # VERY STRONG NEGATIVE:
    # generic job boards / listing pages.
    # ------------------------------------------------------

    listing_terms = [
        "browse jobs",
        "search jobs",
        "job search",
        "jobs in",
        "jobs near",
        "find jobs",
        "job listings",
        "remote jobs",
        "jobs hiring",
        "1000+",
        "100+ jobs",
        "500+ jobs",
        "400+ jobs",
        "3000+ jobs",
    ]

    for term in listing_terms:

        if term in title:
            score -= 10

    # ------------------------------------------------------
    # NEGATIVE:
    # educational / informational articles.
    # ------------------------------------------------------

    article_terms = [
        "what is a data scientist",
        "what does a data scientist do",
        "job description",
        "career guide",
        "career path",
        "definitive guide",
        "interview tips",
        "salary guide",
        "how to become",
        "faq",
    ]

    for term in article_terms:

        if term in title:
            score -= 12

    return score


# ==========================================================
# DEDUPLICATION
# ==========================================================

def deduplicate_results(results):
    """
    Deduplicate results by normalized URL.
    """

    unique = []

    seen = set()

    for result in results:

        url = result.get(
            "url",
            "",
        ).strip()

        if not url:
            continue

        normalized_url = (
            url.rstrip("/")
        )

        if normalized_url in seen:
            continue

        seen.add(
            normalized_url
        )

        unique.append(
            result
        )

    return unique


# ==========================================================
# MAIN JOB SEARCH
# ==========================================================

async def search_jobs(
    message,
    limit=DEFAULT_LIMIT,
):
    """
    Search for real job opportunities using:

        User request
            +
        Career profile
            +
        Existing Tavily web search

    The URLs are supplied by Tavily.
    The function never invents URLs.
    """

    if not message:

        return {
            "status": "error",
            "error": (
                "Job search request is empty."
            ),
            "jobs": [],
        }

    # ------------------------------------------------------
    # Load existing career profile.
    # ------------------------------------------------------

    try:

        profile = load_profile()

    except Exception as error:

        return {
            "status": "error",
            "error": str(error),
            "jobs": [],
        }

    # ------------------------------------------------------
    # Extract request information.
    # ------------------------------------------------------

    role = extract_job_role(
        message
    )

    if not role:

        return {
            "status": "error",
            "error": (
                "Could not determine the job role "
                "from the request."
            ),
            "jobs": [],
        }

    preferences = (
        extract_location_preferences(
            message
        )
    )

    all_profile_skills = (
        extract_profile_skills(
            profile
        )
    )

    relevant_skills = (
        select_relevant_skills(
            role,
            all_profile_skills,
        )
    )

    # ------------------------------------------------------
    # Build targeted queries.
    # ------------------------------------------------------

    queries = build_search_queries(
        role=role,
        preferences=preferences,
        profile_skills=relevant_skills,
    )

    all_results = []

    # ------------------------------------------------------
    # Execute searches.
    # ------------------------------------------------------

    for query in queries:

        try:

            results = await web_search(
                query,
                limit=20,
            )

        except Exception:

            continue

        if not isinstance(
            results,
            list,
        ):
            continue

        all_results.extend(
            results
        )

        if len(all_results) >= MAX_SEARCH_RESULTS:
            break

    # ------------------------------------------------------
    # Filter invalid/non-job results.
    # ------------------------------------------------------

    filtered_results = []

    for result in all_results:

        if not looks_like_job_result(
            result
        ):
            continue

        result = dict(
            result
        )

        result[
            "_search_score"
        ] = score_search_result(
            result
        )

        filtered_results.append(
            result
        )

    # ------------------------------------------------------
    # Remove duplicate URLs.
    # ------------------------------------------------------

    filtered_results = (
        deduplicate_results(
            filtered_results
        )
    )

    # ------------------------------------------------------
    # Rank likely individual job postings first.
    # ------------------------------------------------------

    filtered_results.sort(
        key=lambda item: item.get(
            "_search_score",
            0,
        ),
        reverse=True,
    )

    # ------------------------------------------------------
    # Convert to clean job objects.
    # ------------------------------------------------------

    jobs = []

    for result in filtered_results:

        jobs.append(
            {
                "title": result.get(
                    "title",
                    "",
                ),
                "url": result.get(
                    "url",
                    "",
                ),
                "content": result.get(
                    "content",
                    "",
                ),
                "search_role": role,
                "remote_requested": (
                    preferences[
                        "remote"
                    ]
                ),
                "location_requested": (
                    preferences[
                        "location"
                    ]
                ),
                "search_score": result.get(
                    "_search_score",
                    0,
                ),
            }
        )

        if len(jobs) >= limit:
            break

    return {
        "status": "completed",
        "role": role,
        "preferences": preferences,
        "profile_skill_count": len(
            all_profile_skills
        ),
        "relevant_skills": relevant_skills,
        "queries": queries,
        "jobs": jobs,
    }