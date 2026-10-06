import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from app.agent.job_fetcher import fetch_job_page


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


def _looks_like_specific_job(
    title,
    content,
    json_ld,
):
    """
    Determine whether a page is a specific job vacancy.

    IMPORTANT:

    JSON-LD JobPosting is considered the strongest signal.

    This fixes the previous bug where pages such as:

        Machine Learning Engineer 4 - Capital One

    were incorrectly classified as listing_page despite:

        JSON-LD JOB POSTINGS: 1
    """

    # -------------------------------------------------------------
    # 1. JSON-LD JobPosting = strong confirmation
    # -------------------------------------------------------------

    if json_ld:

        return True

    # -------------------------------------------------------------
    # 2. Reject obvious informational pages
    # -------------------------------------------------------------

    if _looks_like_information_page(
        title,
        content,
    ):

        return False

    # -------------------------------------------------------------
    # 3. Reject obvious broad listing pages
    # -------------------------------------------------------------

    if _looks_like_listing_page(
        title,
        content,
    ):

        return False

    # -------------------------------------------------------------
    # 4. Fallback scoring
    # -------------------------------------------------------------

    score = _specific_job_signals(
        title,
        content,
    )

    return score >= 5


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
    ]

    return any(
        pattern in combined
        for pattern in positive_patterns
    )


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

    fetch_status = page.get("status")

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
        }

    # -------------------------------------------------------------
    # IMPORTANT:
    # fetch_job_page() returns "url", not necessarily "final_url".
    # -------------------------------------------------------------

    final_url = normalize_url(
        page.get("url")
        or page.get("final_url")
        or normalized_url
    )

    if not final_url:

        final_url = normalized_url

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

    json_ld = _get_json_ld_job_postings(
        page
    )

    # -------------------------------------------------------------
    # DEBUG INFORMATION
    # -------------------------------------------------------------

    print(
        "\n--- VERIFY RESULT ---"
    )

    print(
        f"URL: {final_url}"
    )

    print(
        f"TITLE: {title}"
    )

    print(
        f"CONTENT LENGTH: {len(content)}"
    )

    print(
        f"JSON-LD JOB POSTINGS: {len(json_ld)}"
    )

    # -------------------------------------------------------------
    # CRITICAL FIX:
    #
    # JSON-LD JobPosting gets priority over listing detection.
    #
    # Some individual job pages have navigation/footer text
    # containing 'jobs', 'job listings', etc.
    #
    # We must not reject those pages when structured data proves
    # that the page is a JobPosting.
    # -------------------------------------------------------------

    is_specific_job = _looks_like_specific_job(
        title,
        content,
        json_ld,
    )

    if not is_specific_job:

        print(
            "STATUS: listing_page"
        )

        print(
            "JOB STATUS: unknown"
        )

        print(
            "---------------------"
        )

        return {
            "status": "listing_page",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "links": page.get(
                "links",
                [],
            ),
            "job_status": "unknown",
        }

    # -------------------------------------------------------------
    # Determine active / expired status.
    # -------------------------------------------------------------

    job_status = detect_job_status(
        title=title,
        content=content,
        json_ld=json_ld,
    )

    # -------------------------------------------------------------
    # Expired job
    # -------------------------------------------------------------

    if job_status == "expired":

        print(
            "STATUS: expired"
        )

        print(
            "JOB STATUS: expired"
        )

        print(
            "---------------------"
        )

        return {
            "status": "expired",
            "url": final_url,
            "title": title,
            "content": content,
            "json_ld": raw_json_ld,
            "job_posting": json_ld,
            "job_metadata": _extract_job_metadata(
                json_ld
            ),
            "links": page.get(
                "links",
                [],
            ),
            "job_status": "expired",
        }

    # -------------------------------------------------------------
    # VERIFIED JOB
    # -------------------------------------------------------------

    print(
        "STATUS: verified"
    )

    print(
        f"JOB STATUS: {job_status}"
    )

    print(
        "---------------------"
    )

    return {
        "status": "verified",
        "url": final_url,
        "title": title,
        "content": content,
        "json_ld": raw_json_ld,
        "job_posting": json_ld,
        "job_metadata": _extract_job_metadata(
            json_ld
        ),
        "links": page.get(
            "links",
            [],
        ),
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
    Take raw search results and return verified individual
    job vacancies.

    Strategy:

        PASS 1
        Verify direct search result URLs.

        PASS 2
        Inspect a small number of listing pages.

        PASS 3
        Verify individual job links discovered from those pages.

    Concurrency is intentionally limited because some sites require
    browser rendering.
    """

    if not search_results:

        return []

    verified_jobs = []

    seen_urls = set()

    checked_urls = set()

    # -------------------------------------------------------------
    # Keep concurrency small.
    # -------------------------------------------------------------

    semaphore = asyncio.Semaphore(3)

    # =================================================================
    # PASS 1
    # DIRECT SEARCH RESULT URLS
    # =================================================================

    direct_candidates = []

    for search_result in search_results:

        if not isinstance(
            search_result,
            dict,
        ):
            continue

        url = search_result.get(
            "url",
            "",
        )

        title = search_result.get(
            "title",
            "",
        )

        normalized = normalize_url(
            url
        )

        if not normalized:
            continue

        if normalized in checked_urls:
            continue

        checked_urls.add(
            normalized
        )

        direct_candidates.append(
            (
                normalized,
                title,
            )
        )

    print(
        "\n========== VERIFICATION PASS 1 =========="
    )

    print(
        f"DIRECT CANDIDATES: {len(direct_candidates)}"
    )

    async def verify_direct(candidate):

        url, title = candidate

        try:

            async with semaphore:

                result = await asyncio.wait_for(
                    verify_job_url(url),
                    timeout=12,
                )

        except asyncio.TimeoutError:

            print(
                f"TIMEOUT: {url}"
            )

            return None

        except Exception as exc:

            print(
                f"ERROR VERIFYING {url}: {exc}"
            )

            return None

        if not isinstance(
            result,
            dict,
        ):
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
            result.get(
                "url"
            )
            or url
        )

        if not final_url:
            return None

        result[
            "source_title"
        ] = title

        return result

    direct_results = await asyncio.gather(
        *[
            verify_direct(candidate)
            for candidate in direct_candidates
        ],
        return_exceptions=True,
    )

    for result in direct_results:

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

        seen_urls.add(
            final_url
        )

        verified_jobs.append(
            result
        )

        if len(verified_jobs) >= limit:

            print(
                f"DIRECT VERIFIED JOBS: {len(verified_jobs)}"
            )

            return verified_jobs[:limit]

    print(
        f"DIRECT VERIFIED JOBS: {len(verified_jobs)}"
    )

    # =================================================================
    # PASS 2
    # INSPECT LISTING PAGES
    # =================================================================

    listing_candidates = []

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

        if normalized_listing_url in checked_urls:
            continue

        checked_urls.add(
            normalized_listing_url
        )

        listing_candidates.append(
            (
                normalized_listing_url,
                listing_title,
            )
        )

        # ---------------------------------------------------------
        # Only inspect a few listing pages.
        # ---------------------------------------------------------

        if len(listing_candidates) >= 3:
            break

    print(
        f"LISTING PAGES TO INSPECT: {len(listing_candidates)}"
    )

    async def inspect_listing(candidate):

        listing_url, listing_title = candidate

        try:

            async with semaphore:

                page = await asyncio.wait_for(
                    fetch_job_page(
                        listing_url
                    ),
                    timeout=12,
                )

        except asyncio.TimeoutError:

            print(
                f"LISTING TIMEOUT: {listing_url}"
            )

            return []

        except Exception as exc:

            print(
                f"LISTING ERROR: {listing_url} -> {exc}"
            )

            return []

        if page.get(
            "status"
        ) != "success":

            return []

        links = page.get(
            "links",
            [],
        )

        if not isinstance(
            links,
            list,
        ):
            return []

        discovered = []

        for link in links:

            if not isinstance(
                link,
                dict,
            ):
                continue

            link_url = link.get(
                "url",
                "",
            )

            link_text = link.get(
                "text",
                "",
            )

            if not _looks_like_job_link(
                link_url,
                link_text,
            ):
                continue

            absolute_url = urljoin(
                listing_url,
                link_url,
            )

            normalized = normalize_url(
                absolute_url
            )

            if not normalized:
                continue

            if normalized in checked_urls:
                continue

            discovered.append(
                (
                    normalized,
                    listing_title,
                )
            )

            # -----------------------------------------------------
            # Limit links from one listing page.
            # -----------------------------------------------------

            if len(discovered) >= 8:
                break

        print(
            "\n[LISTING PAGE]"
        )

        print(
            f"URL: {listing_url}"
        )

        print(
            f"TITLE: {listing_title}"
        )

        print(
            f"JOB LINKS DISCOVERED: {len(discovered)}"
        )

        return discovered

    listing_results = await asyncio.gather(
        *[
            inspect_listing(candidate)
            for candidate in listing_candidates
        ],
        return_exceptions=True,
    )

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

    print(
        "\n========== DISCOVERY PASS =========="
    )

    print(
        f"TOTAL DISCOVERED JOB LINKS: {len(discovered_candidates)}"
    )

    # =================================================================
    # PASS 3
    # VERIFY DISCOVERED JOB LINKS
    # =================================================================

    print(
        "\n========== VERIFICATION PASS 3 =========="
    )

    print(
        f"DISCOVERED CANDIDATES: {len(discovered_candidates)}"
    )

    async def verify_discovered(candidate):

        url, source_title = candidate

        if url in checked_urls:
            return None

        checked_urls.add(
            url
        )

        try:

            async with semaphore:

                result = await asyncio.wait_for(
                    verify_job_url(url),
                    timeout=12,
                )

        except asyncio.TimeoutError:

            print(
                f"TIMEOUT: {url}"
            )

            return None

        except Exception as exc:

            print(
                f"ERROR: {url} -> {exc}"
            )

            return None

        if not isinstance(
            result,
            dict,
        ):
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
            result.get(
                "url"
            )
            or url
        )

        if not final_url:
            return None

        result[
            "source_title"
        ] = source_title

        return result

    discovered_results = await asyncio.gather(
        *[
            verify_discovered(candidate)
            for candidate in discovered_candidates
        ],
        return_exceptions=True,
    )

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

        # ---------------------------------------------------------
        # Final safety checks.
        #
        # JSON-LD JobPosting has already been given priority, so
        # these checks are intentionally secondary.
        # ---------------------------------------------------------

        result_title = result.get(
            "title",
            "",
        )

        result_content = result.get(
            "content",
            "",
        )

        result_json_ld = _get_json_ld_job_postings(
            result
        )

        if not result_json_ld:

            if _looks_like_information_page(
                result_title,
                result_content,
            ):
                continue

            if _looks_like_listing_page(
                result_title,
                result_content,
            ):
                continue

        seen_urls.add(
            final_url
        )

        verified_jobs.append(
            result
        )

        if len(verified_jobs) >= limit:
            break

    # =================================================================
    # FINAL SUMMARY
    # =================================================================

    print(
        "\n========== JOB VERIFICATION SUMMARY =========="
    )

    print(
        f"RAW JOB COUNT: {len(search_results)}"
    )

    print(
        f"URLS VERIFIED: {len(checked_urls)}"
    )

    print(
        f"LISTING PAGES INSPECTED: {len(listing_candidates)}"
    )

    print(
        f"DISCOVERED JOB LINKS: {len(discovered_candidates)}"
    )

    print(
        f"FINAL VERIFIED JOB COUNT: {len(verified_jobs)}"
    )

    print(
        "=============================================="
    )

    return verified_jobs[:limit]