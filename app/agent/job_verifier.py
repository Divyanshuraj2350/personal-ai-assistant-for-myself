import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from app.agent.job_fetcher import fetch_job_page


# =====================================================================
# BLOCKED DOMAINS
# =====================================================================

BLOCKED_JOB_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "coursera.org",
    "udemy.com",
    "wikipedia.org",
    "medium.com",
    "tricomts.com",
    "em-lyon.com",
}


# =====================================================================
# DOMAIN HELPER
# =====================================================================

def _domain(url):
    """
    Return the normalized hostname for a URL.

    Example:
        https://www.example.com/jobs/123
        -> example.com
    """

    if not url:
        return ""

    try:
        parsed = urlparse(url)

        hostname = (
            parsed.hostname
            or ""
        ).lower().strip()

        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname

    except Exception:
        return ""


# =====================================================================
# URL HELPERS
# =====================================================================

def normalize_url(url):
    """
    Validate and normalize an HTTP/HTTPS URL.
    """

    if not url:
        return ""

    url = str(url).strip()

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return url


# =====================================================================
# JOB STATUS DETECTION
# =====================================================================

EXPIRED_PATTERNS = [
    "this job has expired",
    "job has expired",
    "this vacancy has expired",
    "vacancy has expired",
    "position has been filled",
    "position is no longer available",
    "job is no longer available",
    "job is no longer accepting applications",
    "no longer accepting applications",
    "applications are closed",
    "application deadline has passed",
    "this posting has expired",
    "posting has expired",
    "job posting has expired",
]


ACTIVE_PATTERNS = [
    "apply now",
    "apply for this job",
    "apply for this position",
    "submit application",
    "submit your application",
    "applications are open",
    "accepting applications",
    "apply today",
    "apply here",
    "easy apply",
]


def detect_job_status(title="", content="", json_ld=None):
    """
    Determine whether a job appears active or expired.

    Priority:

    1. JSON-LD validThrough date
    2. Explicit expired text
    3. Explicit active/application text
    4. Unknown
    """

    json_ld = json_ld or []

    # -------------------------------------------------------------
    # 1. Check JSON-LD validThrough
    # -------------------------------------------------------------

    for job in json_ld:

        if not isinstance(job, dict):
            continue

        valid_through = job.get("validThrough")

        if not valid_through:
            continue

        try:

            date_text = str(valid_through).strip()

            # Handle dates such as:
            # 2026-12-31
            # 2026-12-31T23:59:59
            # 2026-12-31T23:59:59Z

            if date_text.endswith("Z"):
                date_text = date_text[:-1] + "+00:00"

            parsed_date = datetime.fromisoformat(date_text)

            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(
                    tzinfo=timezone.utc
                )

            now = datetime.now(timezone.utc)

            if parsed_date < now:
                return "expired"

            return "active"

        except Exception:
            pass

    # -------------------------------------------------------------
    # 2. Explicit expired text
    # -------------------------------------------------------------

    text = f"{title}\n{content}".lower()

    for pattern in EXPIRED_PATTERNS:

        if pattern in text:
            return "expired"

    # -------------------------------------------------------------
    # 3. Explicit active text
    # -------------------------------------------------------------

    for pattern in ACTIVE_PATTERNS:

        if pattern in text:
            return "active"

    # -------------------------------------------------------------
    # 4. Unknown
    # -------------------------------------------------------------

    return "unknown"


# =====================================================================
# JSON-LD HELPERS
# =====================================================================

def _get_json_ld_job_postings(page):
    """
    Extract JobPosting objects from JSON-LD.

    Supports:

        {
            "@type": "JobPosting"
        }

    and:

        {
            "@graph": [
                {
                    "@type": "JobPosting"
                }
            ]
        }
    """

    json_ld_items = page.get("json_ld", [])

    if not isinstance(json_ld_items, list):
        return []

    job_postings = []

    def process_item(item):

        if not isinstance(item, dict):
            return

        item_type = item.get("@type", "")

        if isinstance(item_type, list):

            types = [
                str(value).lower()
                for value in item_type
            ]

        else:

            types = [
                str(item_type).lower()
            ]

        if "jobposting" in types:

            job_postings.append(item)

        # ---------------------------------------------------------
        # Handle @graph
        # ---------------------------------------------------------

        graph = item.get("@graph")

        if isinstance(graph, list):

            for graph_item in graph:

                if not isinstance(graph_item, dict):
                    continue

                graph_type = graph_item.get(
                    "@type",
                    "",
                )

                if isinstance(graph_type, list):

                    graph_types = [
                        str(value).lower()
                        for value in graph_type
                    ]

                else:

                    graph_types = [
                        str(graph_type).lower()
                    ]

                if "jobposting" in graph_types:

                    job_postings.append(graph_item)

    for item in json_ld_items:
        process_item(item)

    # -------------------------------------------------------------
    # Remove duplicate JobPosting objects.
    # -------------------------------------------------------------

    unique = []

    seen = set()

    for job in job_postings:

        key = (
            job.get("url")
            or job.get("identifier")
            or job.get("title")
            or str(job)
        )

        key = str(key)

        if key in seen:
            continue

        seen.add(key)
        unique.append(job)

    return unique


# =====================================================================
# PAGE CLASSIFICATION
# =====================================================================

GENERIC_PAGE_PATTERNS = [
    "career advice",
    "job description",
    "job descriptions",
    "career guide",
    "career profile",
    "working as a",
    "how to become",
    "what does a",
    "what is a",
    "career path",
    "salary guide",
    "salary information",
    "career information",
]


LISTING_TITLE_PATTERNS = [
    "job search",
    "job openings",
    "job opportunities",
    "results for",
    "search results",
    "remote jobs",
    "job board",
    "job listings",
    "find jobs",
    "all jobs",
    "browse jobs",
    "available jobs",
]


def _looks_like_information_page(title, content):
    """
    Detect career articles or informational pages.

    IMPORTANT:
    A real JobPosting found in JSON-LD should be handled before
    this function is used as a hard rejection.
    """

    title_lower = (title or "").strip().lower()

    for pattern in GENERIC_PAGE_PATTERNS:

        if pattern in title_lower:
            return True

    return False


def _looks_like_listing_page(title, content):
    """
    Detect broad job-search/listing pages.

    Does NOT treat every page containing the word 'jobs' as a
    listing page because individual job pages often contain
    that word in navigation/footer content.
    """

    title_lower = (title or "").strip().lower()

    for pattern in LISTING_TITLE_PATTERNS:

        if pattern in title_lower:
            return True

    # Common job-board titles often use a plural "... jobs" even
    # when they do not contain the exact listing phrases above.
    if title_lower.endswith(" jobs") or title_lower.startswith("jobs "):
        return True

    content_lower = (content or "").lower()

    listing_signals = [
        "showing 1-",
        "showing results",
        "search results",
        "browse all jobs",
        "view all jobs",
        "jobs found",
        "results found",
        "hundreds of jobs",
        "100+ jobs",
        "200+ jobs",
        "300+ jobs",
        "400+ jobs",
        "500+ jobs",
    ]

    signal_count = sum(
        1
        for signal in listing_signals
        if signal in content_lower
    )

    return signal_count >= 1


# =====================================================================
# SPECIFIC JOB DETECTION
# =====================================================================

def _specific_job_signals(title, content):
    """
    Count evidence that a page represents one specific vacancy.
    """

    title_lower = (title or "").lower()
    content_lower = (content or "").lower()

    score = 0

    # -------------------------------------------------------------
    # Job-specific title
    # -------------------------------------------------------------

    job_title_patterns = [
        "data scientist",
        "machine learning engineer",
        "machine learning",
        "software engineer",
        "data analyst",
        "backend engineer",
        "frontend engineer",
        "full stack",
        "developer",
        "devops engineer",
        "product manager",
        "business analyst",
        "ai engineer",
        "ml engineer",
        "research scientist",
        "research engineer",
        "ai researcher",
        "deep learning",
        "computer vision",
        "nlp engineer",
        "data engineer",
        "software developer",
    ]

    if any(
        pattern in title_lower
        for pattern in job_title_patterns
    ):
        score += 3

    # -------------------------------------------------------------
    # Strong job metadata
    # -------------------------------------------------------------

    strong_signals = [
        "job id",
        "job requisition",
        "requisition id",
        "requisition number",
        "employment type",
        "employment type:",
        "department",
        "location",
        "job type",
        "job category",
        "date posted",
        "posted on",
        "salary range",
        "pay range",
        "apply now",
        "apply for this job",
        "apply for this position",
        "submit application",
    ]

    for signal in strong_signals:

        if signal in content_lower:
            score += 1

    # -------------------------------------------------------------
    # Individual job sections
    # -------------------------------------------------------------

    section_signals = [
        "about the role",
        "about the job",
        "job responsibilities",
        "responsibilities",
        "qualifications",
        "required qualifications",
        "preferred qualifications",
        "what you'll do",
        "what you will do",
        "requirements",
        "minimum qualifications",
        "basic qualifications",
    ]

    section_count = sum(
        1
        for signal in section_signals
        if signal in content_lower
    )

    if section_count >= 2:

        score += 3

    elif section_count == 1:

        score += 1

    return score


def _looks_like_specific_job(title, content, json_ld):
    """
    Determine whether a page represents one specific job vacancy.

    Priority:

    1. JSON-LD JobPosting
    2. Strong job-specific evidence
    3. Reject generic information/listing pages

    Important:
    A page containing a real JSON-LD JobPosting should NOT be
    rejected merely because its navigation/footer contains words
    such as "jobs", "search results", etc.
    """

    # ----------------------------------------------------------
    # JSON-LD JobPosting is the strongest signal.
    # ----------------------------------------------------------

    if json_ld:
        return True

    # ----------------------------------------------------------
    # Without JSON-LD, reject obvious generic pages.
    # ----------------------------------------------------------

    if _looks_like_information_page(
        title,
        content,
    ):
        return False

    if _looks_like_listing_page(
        title,
        content,
    ):
        return False

    # ----------------------------------------------------------
    # Fall back to content-based scoring.
    # ----------------------------------------------------------

    score = _specific_job_signals(
        title,
        content,
    )

    return score >= 6

# =====================================================================
# JOB LINK DISCOVERY
# =====================================================================

def _looks_like_job_link(url, text=""):
    """
    Determine whether a discovered link looks like an individual
    job page.
    """

    if not url:
        return False

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False

    combined = f"{url} {text}".lower()

    positive_patterns = [
        "/job/",
        "/jobs/",
        "/job-",
        "/jobs-",
        "/careers/",
        "/career/",
        "job-id",
        "jobid",
        "job_id",
        "requisition",
        "req-",
        "offer/",
        "vacancy",
        "position/",
        "opening/",
        "job-detail/",
        "job-detail?",
        "jobs/detail",
        "jobs/view",
        "job/view",
        "job-detail",
        "jobdetail",
        "job-details",
        "jobposting",
        "job-posting",
    ]

    if any(
        pattern in combined
        for pattern in positive_patterns
    ):
        return True

    # Some ATS pages use opaque paths, so URL/text alone may not contain
    # an obvious job keyword. Strong job-action text is a useful discovery
    # fallback; verify_job_url() still decides whether the page is real.
    action_terms = (
        "apply now",
        "apply for this job",
        "apply for this position",
        "view job",
        "job description",
        "requisition",
    )

    return any(term in combined for term in action_terms)


# =====================================================================
# JSON-LD JOB NORMALIZATION
# =====================================================================

def _extract_job_metadata(json_ld):
    """
    Extract useful information from JSON-LD JobPosting.

    This is used to make the final job result more useful.
    """

    if not json_ld:
        return {}

    job = json_ld[0]

    if not isinstance(job, dict):
        return {}

    metadata = {}

    fields = [
        "title",
        "description",
        "datePosted",
        "validThrough",
        "employmentType",
        "url",
        "directApply",
        "hiringOrganization",
        "jobLocation",
        "baseSalary",
    ]

    for field in fields:

        if field in job:

            metadata[field] = job[field]

    return metadata


# =====================================================================
# JSON-LD PAGE MATCHING
# =====================================================================

def _normalize_text(value):
    return " ".join(
        str(value or "").lower().split()
    )


def _job_posting_matches_page(job_posting, final_url, page_title):
    """
    Check whether a JobPosting object appears to describe the
    page being verified instead of an embedded/recommended job.

    A listing page can contain JobPosting JSON-LD for a featured job,
    so the mere presence of JobPosting is not sufficient evidence.
    """

    if not isinstance(job_posting, dict):
        return False

    posting_url = job_posting.get("url")
    posting_title = _normalize_text(
        job_posting.get("title", "")
    )
    current_url = normalize_url(final_url)

    if posting_url and current_url:
        posting_normalized = normalize_url(posting_url)
        if posting_normalized:
            posting_path = urlparse(posting_normalized).path.rstrip("/")
            current_path = urlparse(current_url).path.rstrip("/")
            if posting_normalized == current_url or (
                posting_path
                and current_path
                and posting_path == current_path
            ):
                return True

    page_title = _normalize_text(page_title)

    if posting_title and page_title:
        if posting_title in page_title or page_title in posting_title:
            return True

        posting_words = {
            word
            for word in posting_title.split()
            if len(word) >= 4
        }
        page_words = set(page_title.split())
        overlap = posting_words & page_words

        if len(overlap) >= 2:
            return True

    # If the structured data has no URL/title, do not trust it blindly.
    return False


# =====================================================================
# APPLICATION LINK EXTRACTION
# =====================================================================

def _extract_application_url(links, page_url):
    """
    Find the most likely direct application URL from links discovered
    on the verified job page.

    This function NEVER invents a URL. It only returns a URL that was
    actually present in the fetched page links. If no application link
    is available, the job page URL is returned as a fallback because it
    is still the verified page from which the user can apply.
    """

    if not isinstance(links, list):
        return normalize_url(page_url)

    strong_terms = (
        "apply now",
        "apply for this job",
        "apply for this position",
        "submit application",
        "apply here",
        "easy apply",
        "start application",
        "application",
    )

    candidates = []

    for link in links:
        if not isinstance(link, dict):
            continue

        link_url = normalize_url(link.get("url", ""))
        link_text = str(link.get("text", "") or "").strip().lower()

        if not link_url:
            continue

        if any(term in link_text for term in strong_terms):
            score = 100
            if "apply" in link_text:
                score += 20
            candidates.append((score, link_url))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    return normalize_url(page_url)


# =====================================================================
# SINGLE URL VERIFICATION
# =====================================================================

async def verify_job_url(url):
    """
    Fetch and classify one URL.

    Possible statuses:

        verified
        expired
        listing_page
        insufficient_content
        invalid_url
        error

    Verification priority:

        1. Fetch page
        2. Extract JSON-LD JobPosting
        3. If JSON-LD contains JobPosting -> treat as a real job
        4. Otherwise reject generic/listing pages
        5. Check expired/active status
    """

    normalized_url = normalize_url(url)

    if not normalized_url:

        return {
            "status": "invalid_url",
            "url": url,
            "job_status": "unknown",
        }

    try:

        page = await fetch_job_page(
            normalized_url
        )

    except Exception as exc:

        return {
            "status": "error",
            "url": normalized_url,
            "job_status": "unknown",
            "error": str(exc),
        }

    fetch_status = page.get(
        "status"
    )

    if fetch_status != "success":

        return {
            "status": fetch_status or "error",
            "url": (
                page.get("url")
                or page.get("final_url")
                or normalized_url
            ),
            "title": page.get(
                "title",
                "",
            ),
            "content": page.get(
                "content",
                "",
            ),
            "json_ld": page.get(
                "json_ld",
                [],
            ),
            "links": page.get(
                "links",
                [],
            ),
            "job_status": "unknown",
            "error": page.get(
                "error",
                "",
            ),
        }

    # ----------------------------------------------------------
    # Extract page information.
    # ----------------------------------------------------------

    final_url = (
        page.get("url")
        or page.get("final_url")
        or normalized_url
    )

    title = page.get(
        "title",
        "",
    )

    content = page.get(
        "content",
        "",
    )

    raw_json_ld = page.get(
        "json_ld",
        [],
    )

    links = page.get(
        "links",
        [],
    )

    # ----------------------------------------------------------
    # Extract actual JobPosting objects.
    # ----------------------------------------------------------

    json_ld = _get_json_ld_job_postings(
        page
    )

    print("\n--- VERIFY RESULT ---")
    print("URL:", final_url)
    print("TITLE:", title)
    print(
        "CONTENT LENGTH:",
        len(content or ""),
    )
    print(
        "JSON-LD JOB POSTINGS:",
        len(json_ld),
    )

    # ----------------------------------------------------------
    # IMPORTANT:
    #
    # JSON-LD JobPosting takes priority over listing-page
    # heuristics.
    #
    # Built In, company career pages, etc. can contain words
    # like "jobs" or "search results" in navigation/footer.
    # That should NOT invalidate a page containing a real
    # JobPosting object.
    # ----------------------------------------------------------

    if json_ld:

        # A listing/search page can contain JSON-LD for a featured or
        # recommended vacancy. Only trust the JobPosting when it matches
        # the page URL/title.
        matched_job_postings = [
            posting
            for posting in json_ld
            if _job_posting_matches_page(
                posting,
                final_url,
                title,
            )
        ]

        if matched_job_postings:

            job_status = detect_job_status(
                title=title,
                content=content,
                json_ld=matched_job_postings,
            )

            job_metadata = _extract_job_metadata(
                matched_job_postings
            )

            application_url = _extract_application_url(
                links,
                final_url,
            )

            if job_status == "expired":

                return {
                    "status": "expired",
                    "url": final_url,
                    "title": title,
                    "content": content,
                    "json_ld": raw_json_ld,
                    "job_posting": matched_job_postings,
                    "job_metadata": job_metadata,
                    "links": links,
                    "job_status": "expired",
                }

            return {
                "status": "verified",
                "url": final_url,
                "title": title,
                "content": content,
                "json_ld": raw_json_ld,
                "job_posting": matched_job_postings,
                "job_metadata": job_metadata,
                "application_url": application_url,
                "links": links,
                "job_status": (
                    job_status
                    if job_status != "unknown"
                    else "active"
                ),
            }

    # ----------------------------------------------------------
    # No JSON-LD JobPosting.
    #
    # Now we use normal page classification.
    # ----------------------------------------------------------

    if _looks_like_information_page(
        title,
        content,
    ):

        return {
            "status": "listing_page",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "links": links,
            "job_status": "unknown",
        }

    # ----------------------------------------------------------
    # Reject broad job-search pages.
    # ----------------------------------------------------------

    if _looks_like_listing_page(
        title,
        content,
    ):

        return {
            "status": "listing_page",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "links": links,
            "job_status": "unknown",
        }

    # ----------------------------------------------------------
    # Use content scoring for sites without JSON-LD.
    # ----------------------------------------------------------

    is_specific_job = _looks_like_specific_job(
        title,
        content,
        [],
    )

    if not is_specific_job:

        return {
            "status": "listing_page",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "links": links,
            "job_status": "unknown",
        }

    # ----------------------------------------------------------
    # Check job status.
    # ----------------------------------------------------------

    job_status = detect_job_status(
        title=title,
        content=content,
        json_ld=json_ld,
    )

    application_url = _extract_application_url(
        links,
        final_url,
    )

    # Without structured JobPosting data, require explicit evidence that
    # the vacancy is currently actionable. An application link is enough
    # to upgrade an otherwise unknown page to active.
    if job_status == "unknown" and application_url == final_url:
        return {
            "status": "insufficient_content",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "job_posting": [],
            "job_metadata": {},
            "links": links,
            "job_status": "unknown",
        }

    if job_status == "unknown":
        job_status = "active"

    if job_status == "expired":

        return {
            "status": "expired",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "links": links,
            "job_status": "expired",
        }

    # ----------------------------------------------------------
    # Verified non-JSON-LD job.
    # ----------------------------------------------------------

    return {
        "status": "verified",
        "url": final_url,
        "title": title,
        "content": content,
        "json_ld": raw_json_ld,
        "job_posting": [],
        "job_metadata": {},
        "application_url": application_url,
        "links": links,
        "job_status": job_status,
    }


# =====================================================================
# DISCOVER VERIFIED JOBS
# =====================================================================

async def discover_verified_jobs(
    search_results,
    limit=5,
):
    """
    Convert raw web-search results into verified individual jobs.

    Important:
    - Never allow one slow website to block the entire search.
    - Each URL gets its own timeout.
    - Failed/slow URLs are skipped.
    - Stop as soon as enough verified jobs are found.
    - Listing-page discovery is only used when necessary.
    """

    if not search_results:
        return []

    verified_jobs = []
    seen_urls = set()
    checked_urls = set()

    # Keep this deliberately small.
    semaphore = asyncio.Semaphore(3)

    PER_URL_TIMEOUT = 6
    LISTING_TIMEOUT = 6
    DISCOVERY_TIMEOUT = 6

    # ==========================================================
    # PASS 1
    # DIRECT SEARCH RESULT URLS
    # ==========================================================

    direct_candidates = []

    for search_result in search_results:

        if not isinstance(search_result, dict):
            continue

        url = search_result.get("url", "")
        title = search_result.get("title", "")

        normalized = normalize_url(url)

        if not normalized:
            continue

        if _domain(normalized) in BLOCKED_JOB_DOMAINS:
            continue

        if normalized in checked_urls:
            continue

        checked_urls.add(normalized)

        direct_candidates.append(
            (
                normalized,
                title,
            )
        )

        # Do not verify everything.
        if len(direct_candidates) >= 10:
            break

    print("\n========== VERIFICATION PASS 1 ==========")
    print(
        f"DIRECT CANDIDATES: "
        f"{len(direct_candidates)}"
    )

    async def verify_direct(candidate):

        url, title = candidate

        try:

            async with semaphore:

                result = await asyncio.wait_for(
                    verify_job_url(url),
                    timeout=PER_URL_TIMEOUT,
                )

        except asyncio.TimeoutError:

            print(
                f"[VERIFY TIMEOUT] {url}"
            )

            return None

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            print(
                f"[VERIFY ERROR] "
                f"{url} -> {exc}"
            )

            return None

        if not isinstance(result, dict):
            return None

        if result.get("status") != "verified":
            return None

        if result.get("job_status") == "expired":
            return None

        final_url = normalize_url(
            result.get("url") or url
        )

        if not final_url:
            return None

        result["source_title"] = title

        return result

    # ----------------------------------------------------------
    # Verify in small batches.
    #
    # We intentionally DO NOT launch all URLs at once.
    # ----------------------------------------------------------

    BATCH_SIZE = 3

    for start in range(
        0,
        len(direct_candidates),
        BATCH_SIZE,
    ):

        batch = direct_candidates[
            start:start + BATCH_SIZE
        ]

        print(
            "\n--- VERIFYING BATCH ---"
        )

        print(
            f"CANDIDATES: {len(batch)}"
        )

        tasks = [
            asyncio.create_task(
                verify_direct(candidate)
            )
            for candidate in batch
        ]

        try:

            batch_results = await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        except asyncio.CancelledError:

            for task in tasks:

                if not task.done():
                    task.cancel()

            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

            raise

        for result in batch_results:

            if not isinstance(
                result,
                dict,
            ):
                continue

            if result.get(
                "status"
            ) != "verified":

                continue

            final_url = normalize_url(
                result.get(
                    "url",
                    "",
                )
            )

            if not final_url:
                continue

            if final_url in seen_urls:
                continue

            seen_urls.add(final_url)

            verified_jobs.append(result)

            if len(verified_jobs) >= limit:

                print(
                    f"ENOUGH DIRECT RESULTS: "
                    f"{len(verified_jobs)}"
                )

                print(
                    f"DIRECT VERIFIED JOBS: "
                    f"{len(verified_jobs)}"
                )

                return verified_jobs[:limit]

    print(
        f"DIRECT VERIFIED JOBS: "
        f"{len(verified_jobs)}"
    )

    # ==========================================================
    # PASS 2
    # LISTING PAGES
    # ==========================================================

    listing_candidates = []
    listing_seen = set()

    for search_result in search_results:

        if not isinstance(
            search_result,
            dict,
        ):
            continue

        listing_url = search_result.get(
            "url",
            "",
        )

        listing_title = search_result.get(
            "title",
            "",
        )

        normalized_listing_url = normalize_url(
            listing_url
        )

        if not normalized_listing_url:
            continue

        if (
            _domain(normalized_listing_url)
            in BLOCKED_JOB_DOMAINS
        ):
            continue

        if (
            normalized_listing_url
            in listing_seen
        ):
            continue

        listing_seen.add(
            normalized_listing_url
        )

        listing_candidates.append(
            (
                normalized_listing_url,
                listing_title,
            )
        )

        # Only inspect two listing pages.
        if len(listing_candidates) >= 2:
            break

    print(
        "\n========== VERIFICATION PASS 2 =========="
    )

    print(
        f"LISTING PAGES TO INSPECT: "
        f"{len(listing_candidates)}"
    )

    async def inspect_listing(candidate):

        listing_url, listing_title = candidate

        try:

            async with semaphore:

                page = await asyncio.wait_for(
                    fetch_job_page(
                        listing_url
                    ),
                    timeout=LISTING_TIMEOUT,
                )

        except asyncio.TimeoutError:

            print(
                f"[LISTING TIMEOUT] "
                f"{listing_url}"
            )

            return []

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            print(
                f"[LISTING ERROR] "
                f"{listing_url} -> {exc}"
            )

            return []

        if not isinstance(page, dict):
            return []

        if page.get("status") not in (
            "success",
            "insufficient_content",
        ):
            return []

        links = page.get(
            "links",
            [],
        )

        discovered = []

        for link in links:

            if not isinstance(
                link,
                dict,
            ):
                continue

            url = normalize_url(
                link.get("url", "")
            )

            if not url:
                continue

            if url in checked_urls:
                continue

            if (
                _domain(url)
                in BLOCKED_JOB_DOMAINS
            ):
                continue

            title = link.get(
                "title",
                "",
            )

            discovered.append(
                {
                    "url": url,
                    "title": title,
                    "source_title": (
                        listing_title
                    ),
                }
            )

            if len(discovered) >= 8:
                break

        print(
            f"LISTING PAGE: "
            f"{listing_url}"
        )

        print(
            f"JOB LINKS DISCOVERED: "
            f"{len(discovered)}"
        )

        return discovered

    listing_tasks = [
        asyncio.create_task(
            inspect_listing(candidate)
        )
        for candidate in listing_candidates
    ]

    if listing_tasks:

        try:

            listing_results = await asyncio.gather(
                *listing_tasks,
                return_exceptions=True,
            )

        except asyncio.CancelledError:

            for task in listing_tasks:

                if not task.done():
                    task.cancel()

            await asyncio.gather(
                *listing_tasks,
                return_exceptions=True,
            )

            raise

    else:

        listing_results = []

    discovered_candidates = []

    for result in listing_results:

        if not isinstance(
            result,
            list,
        ):
            continue

        discovered_candidates.extend(
            result
        )

    # Deduplicate discovered URLs.
    unique_discovered = []
    discovered_seen = set()

    for candidate in discovered_candidates:

        url = normalize_url(
            candidate.get(
                "url",
                "",
            )
        )

        if not url:
            continue

        if url in discovered_seen:
            continue

        discovered_seen.add(url)

        unique_discovered.append(
            candidate
        )

    print(
        "\n========== DISCOVERY PASS =========="
    )

    print(
        f"TOTAL DISCOVERED JOB LINKS: "
        f"{len(unique_discovered)}"
    )

    # ==========================================================
    # PASS 3
    # VERIFY DISCOVERED JOB LINKS
    # ==========================================================

    if not unique_discovered:

        print(
            "NO ADDITIONAL JOB LINKS FOUND."
        )

        return verified_jobs[:limit]

    async def verify_discovered(
        candidate
    ):

        url = candidate.get(
            "url",
            "",
        )

        title = candidate.get(
            "title",
            "",
        )

        if not url:
            return None

        try:

            async with semaphore:

                result = await asyncio.wait_for(
                    verify_job_url(url),
                    timeout=DISCOVERY_TIMEOUT,
                )

        except asyncio.TimeoutError:

            print(
                f"[DISCOVERY TIMEOUT] "
                f"{url}"
            )

            return None

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            print(
                f"[DISCOVERY ERROR] "
                f"{url} -> {exc}"
            )

            return None

        if not isinstance(result, dict):
            return None

        if result.get(
            "status"
        ) != "verified":

            return None

        if result.get(
            "job_status"
        ) == "expired":

            return None

        final_url = normalize_url(
            result.get("url") or url
        )

        if not final_url:
            return None

        result["source_title"] = (
            title
        )

        return result

    print(
        "\n========== VERIFICATION PASS 3 =========="
    )

    # Only verify enough candidates to reach
    # the requested limit.
    candidates_to_verify = (
        unique_discovered[:10]
    )

    tasks = [
        asyncio.create_task(
            verify_discovered(candidate)
        )
        for candidate in candidates_to_verify
    ]

    try:

        discovered_results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    except asyncio.CancelledError:

        for task in tasks:

            if not task.done():
                task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        raise

    for result in discovered_results:

        if not isinstance(
            result,
            dict,
        ):
            continue

        if result.get(
            "status"
        ) != "verified":

            continue

        final_url = normalize_url(
            result.get(
                "url",
                "",
            )
        )

        if not final_url:
            continue

        if final_url in seen_urls:
            continue

        seen_urls.add(final_url)

        verified_jobs.append(result)

        if len(verified_jobs) >= limit:
            break

    print(
        "\n========== JOB VERIFICATION SUMMARY =========="
    )

    print(
        f"FINAL VERIFIED JOB COUNT: "
        f"{len(verified_jobs[:limit])}"
    )

    print(
        "=============================================="
    )

    return verified_jobs[:limit]