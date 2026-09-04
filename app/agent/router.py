import re


def detect_intent(message):
    text = message.lower().strip()

    # Calculation
    calculation_patterns = [
        r"^\s*[-+*/%().\d\s]+\s*$",
        r"^\s*(what is|calculate|solve|compute)\s+[-+*/%().\d\s]+\??\s*$",
    ]

    if any(
        re.fullmatch(pattern, text)
        for pattern in calculation_patterns
    ):
        return "calculation"

    # Email
    email_words = [
        "write an email",
        "send an email",
        "email to",
        "mail to",
    ]

    if any(word in text for word in email_words):
        return "email"

    # Job analysis
    job_url = re.search(
        r"https?://[^\s]+",
        message,
        re.IGNORECASE,
    )

    job_words = [
        "analyze this job",
        "analyze the job",
        "analyze this jd",
        "analyze the jd",
        "job description",
        "job posting",
        "job jd",
    ]

    if job_url and any(
        word in text
        for word in job_words
    ):
        return "job_analysis"

    # Social media
    social_words = [
        "post on linkedin",
        "post this on linkedin",
        "post on instagram",
        "post this on instagram",
        "tweet this",
        "post this",
    ]

    if any(word in text for word in social_words):
        return "social"

    # Job search
    job_search_words = [
        "find jobs",
        "find a job",
        "search jobs",
        "job openings",
        "job vacancies",
        "jobs for me",
    ]

    if any(
        word in text
        for word in job_search_words
    ):
        return "job_search"

    # Web / current information
    web_words = [
        "latest",
        "current",
        "today",
        "news",
        "recent",
        "what happened",
        "what is happening",
        "search the web",
        "search online",
        "look it up",
        "find online",
        "according to the internet",
    ]

    if any(
        word in text
        for word in web_words
    ):
        return "web"

    return "chat"