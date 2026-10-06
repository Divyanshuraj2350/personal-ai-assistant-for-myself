import asyncio
import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


# ==========================================================
# CONFIGURATION
# ==========================================================

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

MAX_JOB_CONTENT_LENGTH = 20000

HTTP_CONNECT_TIMEOUT = 4.0
HTTP_READ_TIMEOUT = 6.0
HTTP_WRITE_TIMEOUT = 4.0
HTTP_POOL_TIMEOUT = 4.0
HTTP_TOTAL_TIMEOUT = 10.0

BROWSER_NAVIGATION_TIMEOUT = 15000
BROWSER_RENDER_WAIT = 1000


# ==========================================================
# TEXT CLEANING
# ==========================================================

def clean_job_text(text):
    """
    Normalize extracted job-page text.
    """

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ==========================================================
# TITLE EXTRACTION
# ==========================================================

def _extract_title(html):
    """
    Extract the page title.
    """

    if not html:
        return ""

    try:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        if soup.title:

            return clean_job_text(
                soup.title.get_text(" ")
            )

    except Exception:
        pass

    return ""


# ==========================================================
# JSON-LD EXTRACTION
# ==========================================================

def _extract_json_ld(soup):
    """
    Extract JSON-LD structured data.
    """

    records = []

    try:

        scripts = soup.find_all(
            "script",
            type="application/ld+json",
        )

        for script in scripts:

            raw = script.string

            if not raw:
                raw = script.get_text()

            if not raw:
                continue

            try:

                data = json.loads(raw)

                if isinstance(data, list):

                    records.extend(data)

                else:

                    records.append(data)

            except Exception:

                continue

    except Exception:

        pass

    return records


# ==========================================================
# METADATA EXTRACTION
# ==========================================================

def _extract_metadata(soup):
    """
    Extract useful metadata from a page.
    """

    metadata = []

    try:

        for tag in soup.find_all(
            "meta"
        ):

            name = (
                tag.get("name")
                or tag.get("property")
                or tag.get("itemprop")
                or ""
            )

            content = (
                tag.get("content")
                or ""
            )

            if not content:
                continue

            name = name.strip()

            if name.lower() in {
                "description",
                "og:title",
                "og:description",
                "twitter:title",
                "twitter:description",
                "description",
            }:

                metadata.append(
                    clean_job_text(content)
                )

    except Exception:

        pass

    return metadata


# ==========================================================
# PAGE CONTENT EXTRACTION
# ==========================================================

def _extract_page_content(
    html,
    base_url="",
):
    """
    Extract readable content, links and JSON-LD
    from a job page.
    """

    if not html:

        return {
            "content": "",
            "links": [],
            "json_ld": [],
        }

    try:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

    except Exception:

        return {
            "content": "",
            "links": [],
            "json_ld": [],
        }

    # ------------------------------------------------------
    # JSON-LD
    # ------------------------------------------------------

    json_ld_records = _extract_json_ld(
        soup
    )

    json_ld_text = ""

    if json_ld_records:

        try:

            json_ld_text = json.dumps(
                json_ld_records,
                ensure_ascii=False,
            )

        except Exception:

            json_ld_text = ""

    # ------------------------------------------------------
    # Metadata
    # ------------------------------------------------------

    metadata = _extract_metadata(
        soup
    )

    # ------------------------------------------------------
    # Links
    # ------------------------------------------------------

    links = []

    try:

        for element in soup.find_all(
            "a",
            href=True,
        ):

            href = element.get(
                "href"
            )

            if not href:
                continue

            absolute_url = urljoin(
                base_url,
                href,
            )

            if absolute_url not in links:

                links.append(
                    absolute_url
                )

    except Exception:

        pass

    # ------------------------------------------------------
    # Remove useless HTML
    # ------------------------------------------------------

    text_soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for element in text_soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
            "svg",
        ]
    ):

        element.decompose()

    # ------------------------------------------------------
    # Readable body text
    # ------------------------------------------------------

    body_text = clean_job_text(
        text_soup.get_text(" ")
    )

    # ------------------------------------------------------
    # Combine useful content
    # ------------------------------------------------------

    parts = []

    if json_ld_text:

        parts.append(
            json_ld_text
        )

    if metadata:

        parts.extend(
            metadata
        )

    if body_text:

        parts.append(
            body_text
        )

    combined_text = clean_job_text(
        " ".join(parts)
    )

    # ------------------------------------------------------
    # Limit content size
    # ------------------------------------------------------

    if (
        len(combined_text)
        > MAX_JOB_CONTENT_LENGTH
    ):

        combined_text = (
            combined_text[
                :MAX_JOB_CONTENT_LENGTH
            ]
            + "..."
        )

    return {
        "content": combined_text,
        "links": links,
        "json_ld": json_ld_records,
    }


# ==========================================================
# JOB CONTENT VALIDATION
# ==========================================================

def _is_meaningful_job_content(
    content
):
    """
    Determine whether extracted page content
    contains enough information to be useful.
    """

    if not content:
        return False

    text = content.lower()

    if len(content) < 500:
        return False

    job_keywords = [
        "job",
        "career",
        "employment",
        "responsibilities",
        "qualifications",
        "requirements",
        "experience",
        "skills",
        "machine learning",
        "software engineer",
        "data scientist",
        "artificial intelligence",
        "apply",
    ]

    matches = sum(
        1
        for keyword in job_keywords
        if keyword in text
    )

    return matches >= 2


# ==========================================================
# HTTP FETCH
# ==========================================================

async def _fetch_with_httpx(url):
    """
    Normal HTTP fetch with a hard timeout.
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9"
        ),
        "Cache-Control": "no-cache",
    }

    timeout = httpx.Timeout(
        connect=3.0,
        read=7.0,
        write=5.0,
        pool=3.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:

        response = await client.get(url)

        response.raise_for_status()

        return (
            str(response.url),
            response.text,
        )


# ==========================================================
# BROWSER FETCH
# ==========================================================

async def _fetch_with_browser(url):
    """
    Render JavaScript-heavy job pages.

    Uses DOMContentLoaded rather than networkidle.
    """

    try:

        from playwright.async_api import (
            async_playwright,
        )

    except ImportError:

        return (
            None,
            None,
            "Playwright is not installed.",
        )

    try:

        async with async_playwright() as playwright:

            browser = await playwright.chromium.launch(
                headless=True
            )

            try:

                page = await browser.new_page(
                    user_agent=USER_AGENT
                )

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=7000,
                )

                await page.wait_for_timeout(
                    500
                )

                rendered_html = (
                    await page.content()
                )

                final_url = page.url

                return (
                    final_url,
                    rendered_html,
                    None,
                )

            finally:

                await browser.close()

    except Exception as exc:

        return (
            None,
            None,
            str(exc),
        )


# ==========================================================
# MAIN JOB PAGE FETCHER
# ==========================================================

async def fetch_job_page(url):
    """
    Fetch a job/application page.

    Strategy:

    1. Normal HTTP request.
    2. Extract readable text and structured data.
    3. If HTTP content is insufficient, use browser rendering.
    4. Never allow one bad URL to crash the entire pipeline.
    """

    if not url:

        return {
            "status": "error",
            "error": "No job URL provided.",
        }

    # ======================================================
    # PASS 1: NORMAL HTTP
    # ======================================================

    try:

        final_url, html_content = (
            await _fetch_with_httpx(url)
        )

    except asyncio.CancelledError:

        raise

    except Exception as exc:

        print(
            f"[JOB FETCHER] HTTP failed: {url}"
        )

        print(
            f"[JOB FETCHER] Reason: {exc}"
        )

        # --------------------------------------------------
        # HTTP failed.
        #
        # Try browser rendering as a fallback.
        # --------------------------------------------------

        (
            browser_url,
            browser_html,
            browser_error,
        ) = await _fetch_with_browser(
            url
        )

        if browser_html:

            final_url = (
                browser_url
                or url
            )

            html_content = (
                browser_html
            )

        else:

            return {
                "status": "error",
                "url": url,
                "error": (
                    f"HTTP fetch failed: {exc}; "
                    f"Browser fallback failed: "
                    f"{browser_error}"
                ),
            }

    # ======================================================
    # PASS 2: EXTRACT HTTP/BROWSER CONTENT
    # ======================================================

    try:

        extracted = _extract_page_content(
            html_content,
            final_url,
        )

        content = extracted[
            "content"
        ]

        if _is_meaningful_job_content(
            content
        ):

            return {
                "status": "success",
                "url": final_url,
                "title": _extract_title(
                    html_content
                ),
                "content": content,
                "links": extracted[
                    "links"
                ],
                "json_ld": extracted[
                    "json_ld"
                ],
                "rendered": False,
            }

    except Exception as exc:

        print(
            f"[JOB FETCHER] Extraction failed: "
            f"{final_url}"
        )

        print(
            f"[JOB FETCHER] Reason: {exc}"
        )


    # ======================================================
    # PASS 3: BROWSER FALLBACK
    # ======================================================

    try:

        (
            browser_url,
            browser_html,
            browser_error,
        ) = await _fetch_with_browser(
            final_url
        )

        if browser_html:

            browser_final_url = (
                browser_url
                or final_url
            )

            browser_extracted = (
                _extract_page_content(
                    browser_html,
                    browser_final_url,
                )
            )

            browser_content = (
                browser_extracted[
                    "content"
                ]
            )

            if _is_meaningful_job_content(
                browser_content
            ):

                return {
                    "status": "success",
                    "url": browser_final_url,
                    "title": _extract_title(
                        browser_html
                    ),
                    "content": (
                        browser_content
                    ),
                    "links": (
                        browser_extracted[
                            "links"
                        ]
                    ),
                    "json_ld": (
                        browser_extracted[
                            "json_ld"
                        ]
                    ),
                    "rendered": True,
                }

        # --------------------------------------------------
        # Browser was attempted but no useful content.
        # --------------------------------------------------

        return {
            "status": "error",
            "url": final_url,
            "error": (
                "Could not extract meaningful "
                "job content."
            ),
            "browser_error": browser_error,
        }

    except asyncio.CancelledError:

        raise

    except Exception as exc:

        return {
            "status": "error",
            "url": final_url,
            "error": (
                f"Browser fetch failed: {exc}"
            ),
        }