from pathlib import Path

from playwright.async_api import async_playwright


def _selector_candidates(field):
    field_id = field.get("field_id")
    field_name = field.get("field_name")

    selectors = []

    if field_id:
        selectors.append(f"#{field_id}")

    if field_name:
        escaped_name = field_name.replace("\\", "\\\\").replace('"', '\\"')
        selectors.append(f'[name="{escaped_name}"]')

    return selectors


async def _find_locator(page, field):
    for selector in _selector_candidates(field):
        locator = page.locator(selector)

        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            continue

    return None


async def _fill_field(page, field):
    action = field.get("action")
    field_type = (field.get("type") or "").lower()
    value = field.get("value")

    if action != "fill":
        return {
            "field_name": field.get("field_name"),
            "label": field.get("label"),
            "status": "skipped",
            "reason": f"Action is '{action}', not 'fill'.",
        }

    if value is None:
        return {
            "field_name": field.get("field_name"),
            "label": field.get("label"),
            "status": "skipped",
            "reason": "No value supplied.",
        }

    locator = await _find_locator(page, field)

    if locator is None:
        return {
            "field_name": field.get("field_name"),
            "label": field.get("label"),
            "status": "error",
            "reason": "Field could not be located.",
        }

    try:
        if field_type == "file":
            path = Path(str(value)).expanduser().resolve()

            if not path.is_file():
                return {
                    "field_name": field.get("field_name"),
                    "label": field.get("label"),
                    "status": "error",
                    "reason": f"Resume file does not exist: {path}",
                }

            await locator.set_input_files(str(path))

            return {
                "field_name": field.get("field_name"),
                "label": field.get("label"),
                "status": "filled",
                "action": "upload",
                "path": str(path),
            }

        if field_type == "checkbox":
            return {
                "field_name": field.get("field_name"),
                "label": field.get("label"),
                "status": "skipped",
                "reason": "Checkboxes are never automatically enabled.",
            }

        await locator.fill(str(value))

        return {
            "field_name": field.get("field_name"),
            "label": field.get("label"),
            "status": "filled",
            "action": "fill",
        }

    except Exception as exc:
        return {
            "field_name": field.get("field_name"),
            "label": field.get("label"),
            "status": "error",
            "reason": str(exc),
        }


async def fill_application_form(
    application_result,
    proposal,
    headless=True,
):
    """
    Fill an application form using an approved proposal.

    Safety rules:
    - Only fields with action='fill' are filled.
    - Resume upload occurs only when a real file path is supplied.
    - Consent checkboxes are never enabled automatically.
    - Manual-review fields are never filled.
    - The Submit button is never clicked.
    """

    if not isinstance(application_result, dict):
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["Invalid application result."],
        }

    if not isinstance(proposal, dict):
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["Invalid application proposal."],
        }

    if application_result.get("status") != "success":
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["Application detection did not succeed."],
        }

    if not application_result.get("is_application_form"):
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["Target is not an application form."],
        }

    if proposal.get("status") != "success":
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["Application proposal was not successful."],
        }

    # Never allow unresolved required fields into browser filling.
    unresolved = proposal.get("unresolved_required_fields", [])

    if unresolved:
        return {
            "status": "blocked",
            "filled": False,
            "submitted": False,
            "errors": [
                "Application has unresolved required fields."
            ],
            "unresolved_required_fields": unresolved,
        }

    url = (
        application_result.get("final_url")
        or application_result.get("url")
    )

    if not url:
        return {
            "status": "error",
            "filled": False,
            "submitted": False,
            "errors": ["No application URL available."],
        }

    results = []
    errors = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless
        )

        page = await browser.new_page()

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.wait_for_timeout(1500)

            page_title = await page.title()

            if "404" in page_title.lower() or "not found" in page_title.lower():

                return {
                    "status": "error",
                    "filled": False,
                    "submitted": False,
                    "submission_performed": False,
                    "url": url,
                    "final_url": page.url,
                    "title": page_title,
                    "errors": [
                        "Application page returned a 404/not-found page."
                    ],
                }

            form_count = await page.locator("form").count()

            if form_count == 0:

                return {
                    "status": "error",
                    "filled": False,
                    "submitted": False,
                    "submission_performed": False,
                    "url": url,
                    "final_url": page.url,
                    "title": page_title,
                    "errors": [
                        "No application form was found on the loaded page."
                    ],
                }

            # Only process fields explicitly marked as fill.
            for field in proposal.get("fields", []):
                if field.get("action") == "fill":
                    result = await _fill_field(page, field)
                    results.append(result)

                    if result.get("status") == "error":
                        errors.append(result.get("reason"))

            # IMPORTANT:
            # Do not submit.
            # Do not click any submit/application button.
            await page.wait_for_timeout(500)

            return {
                "status": "success" if not errors else "partial",
                "filled": True,
                "submitted": False,
                "submission_performed": False,
                "url": url,
                "final_url": page.url,
                "title": await page.title(),
                "field_results": results,
                "filled_count": sum(
                    1
                    for item in results
                    if item.get("status") == "filled"
                ),
                "error_count": len(errors),
                "errors": errors,
                "safety": {
                    "submit_clicked": False,
                    "consent_checked": False,
                    "manual_review_fields_filled": False,
                },
            }

        except Exception as exc:
            return {
                "status": "error",
                "filled": False,
                "submitted": False,
                "submission_performed": False,
                "errors": [str(exc)],
            }

        finally:
            await browser.close()
