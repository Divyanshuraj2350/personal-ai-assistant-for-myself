import asyncio
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


APPLICATION_SIGNALS = [
    "apply",
    "application",
    "candidate",
    "job application",
    "submit application",
]


def _clean(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


async def _get_label(page, element):
    try:
        element_id = await element.get_attribute("id")

        if element_id:
            label = page.locator(f'label[for="{element_id}"]').first
            if await label.count():
                text = await label.inner_text()
                if _clean(text):
                    return _clean(text)
    except Exception:
        pass

    try:
        parent_label = element.locator("xpath=ancestor::label[1]")
        if await parent_label.count():
            text = await parent_label.inner_text()
            if _clean(text):
                return _clean(text)
    except Exception:
        pass

    return ""


async def _inspect_field(page, element):
    try:
        field_type = await element.get_attribute("type") or "text"
        name = await element.get_attribute("name") or ""
        field_id = await element.get_attribute("id") or ""
        placeholder = await element.get_attribute("placeholder") or ""
        required = await element.get_attribute("required") is not None

        aria_label = await element.get_attribute("aria-label") or ""
        autocomplete = await element.get_attribute("autocomplete") or ""

        label = await _get_label(page, element)

        if not label:
            label = aria_label

        return {
            "tag": await element.evaluate("(el) => el.tagName.toLowerCase()"),
            "type": _clean(field_type),
            "name": _clean(name),
            "id": _clean(field_id),
            "label": _clean(label),
            "placeholder": _clean(placeholder),
            "autocomplete": _clean(autocomplete),
            "required": required,
        }

    except Exception:
        return None


async def inspect_application_form(url):
    """
    Inspect a job application page without filling or submitting anything.
    """

    if not isinstance(url, str) or not url.strip():
        return {
            "status": "error",
            "message": "Application URL is required.",
        }

    url = url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return {
            "status": "error",
            "message": "Only HTTP/HTTPS URLs are supported.",
        }

    browser = None

    try:
        async with async_playwright() as playwright:

            browser = await playwright.chromium.launch(
                headless=True
            )

            page = await browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 1000,
                }
            )

            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            except PlaywrightTimeoutError:
                return {
                    "status": "timeout",
                    "is_application_form": False,
                    "url": url,
                    "message": "Application page timed out while loading.",
                }

            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=10000,
                )
            except PlaywrightTimeoutError:
                pass

            final_url = page.url
            title = _clean(await page.title())

            body_text = ""
            try:
                body_text = _clean(
                    await page.locator("body").inner_text()
                )
            except Exception:
                pass

            body_lower = body_text.lower()
            title_lower = title.lower()

            signal_matches = []

            for signal in APPLICATION_SIGNALS:
                if signal in body_lower or signal in title_lower:
                    signal_matches.append(signal)

            forms = page.locator("form")
            form_count = await forms.count()

            fields = []

            inputs = page.locator(
                "input:not([type='hidden']):not([disabled])"
            )

            for i in range(await inputs.count()):
                field = await _inspect_field(
                    page,
                    inputs.nth(i),
                )

                if field:
                    fields.append(field)

            textareas = page.locator(
                "textarea:not([disabled])"
            )

            for i in range(await textareas.count()):
                field = await _inspect_field(
                    page,
                    textareas.nth(i),
                )

                if field:
                    fields.append(field)

            selects = page.locator(
                "select:not([disabled])"
            )

            for i in range(await selects.count()):
                field = await _inspect_field(
                    page,
                    selects.nth(i),
                )

                if field:
                    fields.append(field)

            submit_count = await page.locator(
                "button[type='submit'], input[type='submit']"
            ).count()

            is_application_form = (
                form_count > 0
                and len(fields) > 0
                and (
                    len(signal_matches) >= 1
                    or submit_count > 0
                )
            )

            return {
                "status": "success",
                "is_application_form": is_application_form,
                "url": url,
                "final_url": final_url,
                "title": title,
                "http_status": (
                    response.status
                    if response
                    else None
                ),
                "form_count": form_count,
                "field_count": len(fields),
                "submit_control_count": submit_count,
                "application_signals": signal_matches,
                "fields": fields,
            }

    except Exception as exc:
        return {
            "status": "error",
            "is_application_form": False,
            "url": url,
            "message": str(exc),
        }

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


def inspect_application_form_sync(url):
    """
    Synchronous wrapper for simple tests.
    """
    return asyncio.run(
        inspect_application_form(url)
    )
