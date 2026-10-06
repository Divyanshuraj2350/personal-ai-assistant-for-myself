import re


# ==========================================================
# INTENTS
# ==========================================================

INTENTS = [
    "chat",
    "calculation",
    "email",
    "job_analysis",
    "job_search",
    "social",
    "web",
]


# ==========================================================
# KNOWLEDGE SOURCE KEYWORDS
# ==========================================================

WEB_WORDS = [
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

RAG_WORDS = [
    "my project",
    "my report",
    "my resume",
    "my cv",
    "my notes",
    "my document",
    "my pdf",
    "my files",
    "uploaded document",
    "uploaded file",
    "according to my report",
    "according to my project",
    "in my report",
    "in my project",
    "in my resume",
    "from the report",
    "from the document",
]


# ==========================================================
# BASIC HELPERS
# ==========================================================

def _contains_any(text, words):
    return any(word in text for word in words)


def _is_pure_math(text):
    """
    Examples:

        25*50
        100 / 5
        (20 + 10) * 2
        50%10
    """

    return bool(
        re.fullmatch(
            r"\s*[-+*/%().\d\s]+\s*",
            text,
        )
    )


def _contains_math_expression(text):
    """
    Detect math expressions inside natural language.

    Examples:

        what is 25*50
        calculate 10 + 20
        solve 100/5
    """

    return bool(
        re.search(
            r"\d+\s*[-+*/%]\s*\d+",
            text,
        )
    )


def _has_url(message):
    return bool(
        re.search(
            r"https?://[^\s]+",
            message,
            re.IGNORECASE,
        )
    )


# ==========================================================
# KNOWLEDGE SOURCE DETECTION
# ==========================================================

def _has_explicit_web_request(text):
    return _contains_any(
        text,
        WEB_WORDS,
    )


def _has_personal_document_request(text):
    if _contains_any(
        text,
        RAG_WORDS,
    ):
        return True

    if re.search(
        r"\bmy\b(?:\s+\w+){0,5}\s+\bproject\b",
        text,
    ):
        return True

    if re.search(
        r"\bmy\b(?:\s+\w+){0,5}\s+"
        r"\b(report|document|pdf|notes|file)\b",
        text,
    ):
        return True

    return False


def _looks_like_new_external_topic(message):
    """
    Detect questions about new/versioned topics.

    Examples:

        What is Python 3.14?
        Tell me about GPT-6
        What is Model X2?
        What is the new OpenAI model?
    """

    text = message.lower().strip()

    question_words = [
        "tell me about",
        "what is",
        "what are",
        "who is",
        "explain",
        "information about",
        "details about",
    ]

    if not _contains_any(
        text,
        question_words,
    ):
        return False

    versioned_topic = re.search(
        r"\b[a-zA-Z][a-zA-Z0-9_-]*[-.]?\s*\d+"
        r"(?:\.\d+)?\b",
        message,
    )

    if versioned_topic:
        return True

    freshness_words = [
        "new",
        "newly",
        "released",
        "release",
        "launched",
        "launch",
        "announced",
        "announcement",
        "recently introduced",
    ]

    return _contains_any(
        text,
        freshness_words,
    )


def detect_knowledge_source(message):
    """
    Decide where knowledge should come from.

    Priority:

        1. Personal document
        2. Explicit web/current information
        3. New/versioned external topic
        4. Qwen
    """

    text = message.lower().strip()

    # Personal documents have highest priority.
    if _has_personal_document_request(text):
        return "rag"

    # Explicit web request.
    if _has_explicit_web_request(text):
        return "web"

    # New/versioned external topic.
    if _looks_like_new_external_topic(message):
        return "web"

    # Normal question → Qwen.
    return "qwen"


# ==========================================================
# JOB SEARCH DETECTION
# ==========================================================

JOB_WORDS = [
    "job",
    "jobs",
    "internship",
    "internships",
    "opening",
    "openings",
    "vacancy",
    "vacancies",
    "position",
    "positions",
    "opportunity",
    "opportunities",
]


JOB_SEARCH_ACTIONS = [
    "find",
    "search",
    "look for",
    "show",
    "get me",
]


def _has_job_term(text):
    return _contains_any(
        text,
        JOB_WORDS,
    )


def _has_job_search_action(text):
    return _contains_any(
        text,
        JOB_SEARCH_ACTIONS,
    )


def _is_job_search_request(text):
    """
    Examples:

        search for Python internships
        find me ML jobs
        look for backend jobs
        show me software engineering openings
    """

    if not _has_job_term(text):
        return False

    if _has_job_search_action(text):
        return True

    explicit_search = re.search(
        r"\bsearch\s+(for\s+)?"
        r"(?:[\w./+-]+\s+){0,6}"
        r"(jobs?|internships?|vacancies?|openings?)\b",
        text,
    )

    return bool(explicit_search)


# ==========================================================
# JOB ANALYSIS DETECTION
# ==========================================================

JOB_ANALYSIS_WORDS = [
    "analyze this job",
    "analyze the job",
    "analyze this jd",
    "analyze the jd",
    "analyze this job description",
    "analyze this job posting",
    "analyze job",
    "analyze the job description",
]


def _is_job_analysis_request(message):
    text = message.lower()

    if _contains_any(
        text,
        JOB_ANALYSIS_WORDS,
    ):
        return True

    # URL + analyze
    if (
        _has_url(message)
        and "analy" in text
        and (
            "job" in text
            or "jd" in text
            or "posting" in text
        )
    ):
        return True

    return False


# ==========================================================
# EMAIL DETECTION
# ==========================================================

EMAIL_WORDS = [
    "write an email",
    "send an email",
    "draft an email",
    "compose an email",
    "write a mail",
    "send a mail",
    "draft a mail",
    "compose a mail",
    "email to",
    "mail to",
]


def _is_email_request(text):
    return _contains_any(
        text,
        EMAIL_WORDS,
    )


# ==========================================================
# SOCIAL DETECTION
# ==========================================================

SOCIAL_WORDS = [
    "post on linkedin",
    "post this on linkedin",
    "publish on linkedin",
    "post on instagram",
    "post this on instagram",
    "publish on instagram",
    "tweet this",
    "post this",
]


def _is_social_request(text):
    return _contains_any(
        text,
        SOCIAL_WORDS,
    )


# ==========================================================
# CALCULATION DETECTION
# ==========================================================

CALCULATION_WORDS = [
    "calculate",
    "compute",
    "solve",
    "do the math",
]


def _is_calculation_request(text):
    if _is_pure_math(text):
        return True

    if _contains_math_expression(text):
        return True

    if _contains_any(
        text,
        CALCULATION_WORDS,
    ):
        return True

    return False


# ==========================================================
# INTENT DETECTION
# ==========================================================

def detect_intent(message):
    """
    Simple deterministic intent router.

    Priority:

        calculation
        job analysis
        job search
        email
        social
        web
        chat
    """

    if not message:
        return "chat"

    text = message.lower().strip()

    # ------------------------------------------------------
    # 1. CALCULATION
    # ------------------------------------------------------

    if _is_calculation_request(text):
        return "calculation"

    # ------------------------------------------------------
    # 2. JOB ANALYSIS
    # ------------------------------------------------------

    if _is_job_analysis_request(message):
        return "job_analysis"

    # ------------------------------------------------------
    # 3. JOB SEARCH
    # ------------------------------------------------------

    if _is_job_search_request(text):
        return "job_search"

    # ------------------------------------------------------
    # 4. EMAIL
    # ------------------------------------------------------

    if _is_email_request(text):
        return "email"

    # ------------------------------------------------------
    # 5. SOCIAL
    # ------------------------------------------------------

    if _is_social_request(text):
        return "social"

    # ------------------------------------------------------
    # 6. WEB
    # ------------------------------------------------------

    if _has_explicit_web_request(text):
        return "web"

    if _looks_like_new_external_topic(message):
        return "web"

    # ------------------------------------------------------
    # 7. NORMAL CHAT / QWEN
    # ------------------------------------------------------

    return "chat"


# ==========================================================
# SIMPLE PROBABILITIES
# ==========================================================

def get_intent_probabilities(message):
    """
    Return a simple confidence distribution.

    These are routing scores, not ML probabilities.
    """

    intent = detect_intent(message)

    probabilities = {
        name: 0.0
        for name in INTENTS
    }

    confidence_map = {
        "calculation": 0.95,
        "job_analysis": 0.95,
        "job_search": 0.95,
        "email": 0.95,
        "social": 0.95,
        "web": 0.90,
        "chat": 0.90,
    }

    probabilities[intent] = confidence_map[
        intent
    ]

    remaining = 1.0 - probabilities[intent]

    other_intents = [
        name
        for name in INTENTS
        if name != intent
    ]

    if other_intents and remaining > 0:
        small_value = (
            remaining / len(other_intents)
        )

        for name in other_intents:
            probabilities[name] = small_value

    return dict(
        sorted(
            probabilities.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


# ==========================================================
# ROUTING CONFIDENCE
# ==========================================================

def get_routing_confidence(message):
    probabilities = get_intent_probabilities(
        message
    )

    ranked = list(
        probabilities.items()
    )

    best_intent = ranked[0][0]
    best_probability = ranked[0][1]

    if len(ranked) > 1:
        second_intent = ranked[1][0]
        second_probability = ranked[1][1]
    else:
        second_intent = None
        second_probability = 0.0

    margin = (
        best_probability
        - second_probability
    )

    return {
        "intent": best_intent,
        "confidence": round(
            best_probability,
            4,
        ),
        "second_intent": second_intent,
        "second_probability": round(
            second_probability,
            4,
        ),
        "margin": round(
            margin,
            4,
        ),
        "probabilities": probabilities,
    }


# ==========================================================
# COMPOUND REQUEST DETECTION
# ==========================================================

def detect_compound_intents(message):
    """
    Detect only the compound requests that the application
    currently knows how to execute safely.

    Currently supported:

        job search + job analysis

    Example:

        search latest ML jobs and analyze them

    Returns:

        ["job_search", "job_analysis"]
    """

    text = message.lower().strip()

    has_search = _is_job_search_request(
        text
    )

    has_analysis = (
        "analy" in text
        and (
            "job" in text
            or "jd" in text
            or "them" in text
        )
    )

    if has_search and has_analysis:
        return [
            "job_search",
            "job_analysis",
        ]

    return []


# ==========================================================
# UNIFIED ROUTING DECISION
# ==========================================================

def get_routing_decision(message):
    """
    Main routing decision used by the application.

    Returns:

        {
            "intent": ...,
            "confidence": ...,
            "knowledge_source": ...,
            "compound": ...,
            "secondary_intents": ...,
            "probabilities": ...
        }
    """

    if not message:
        message = ""

    primary_intent = detect_intent(
        message
    )

    knowledge_source = detect_knowledge_source(
        message
    )

    compound_intents = detect_compound_intents(
        message
    )

    compound = bool(
        compound_intents
    )

    # ------------------------------------------------------
    # COMPOUND JOB REQUEST
    # ------------------------------------------------------

    if compound:
        primary_intent = "job_search"

        secondary_intents = [
            "job_analysis"
        ]

        # Fresh job data must come from web.
        text = message.lower()

        if (
            _has_explicit_web_request(text)
            or "latest" in text
            or "current" in text
            or "today" in text
            or "recent" in text
            or "online" in text
        ):
            knowledge_source = "web"

    else:
        secondary_intents = []

    # ------------------------------------------------------
    # IMPORTANT OVERRIDES
    # ------------------------------------------------------

    # Calculation never needs web.
    if primary_intent == "calculation":
        knowledge_source = "qwen"

    # Job search needs web when the user asks for current
    # or explicitly online jobs.
    if primary_intent == "job_search":
        knowledge_source = "web"

    # Job analysis of a URL needs the URL/page itself.
    if primary_intent == "job_analysis":
        knowledge_source = "web"

    # ------------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------------

    probabilities = get_intent_probabilities(
        message
    )

    confidence = probabilities.get(
        primary_intent,
        0.0,
    )

    # Compound requests have a slightly lower primary
    # confidence because two actions are involved.
    if compound:
        confidence = 0.90

    # ------------------------------------------------------
    # FINAL RESULT
    # ------------------------------------------------------

    return {
        "intent": primary_intent,
        "confidence": round(
            confidence,
            4,
        ),
        "knowledge_source": knowledge_source,
        "compound": compound,
        "secondary_intents": secondary_intents,
        "probabilities": probabilities,
    }