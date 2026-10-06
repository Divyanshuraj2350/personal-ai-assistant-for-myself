import asyncio
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


APPLICATION_SIGNALS = [
    "apply",
    "application",
    "candidate",
    "job application",
    "submit application",
    "start application",
]


APPLICATION_LINK_SIGNALS = [
    "apply",
    "apply now",
    "apply for this job",
    "application",
    "start application",
    "submit application",
]


IGNORE_FIELD_SIGNALS = [
    "cookie",
    "cookies",
    "search",
    "analytics",
    "tracking",
    "marketing",
    "advertising",
    "vendor",
    "privacy",
    "consent",
    "newsletter",
]


def _clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def _contains_signal(value, signals):
    value = _clean(value).lower()

    return any(
        signal in value
        for signal in signals
    )


def _looks_like_candidate_field(field):
    combined = " ".join(
        [
            field.get("name", ""),
            field.get("id", ""),
            field.get("label", ""),
            field.get("placeholder", ""),
            field.get("autocomplete", ""),
            field.get("aria_label", ""),
            field.get("automation_id", ""),
            field.get("qa", ""),
        ]
    ).lower()

    if not combined.strip():
        return False

    if _contains_signal(
        combined,
        IGNORE_FIELD_SIGNALS,
    ):
        return False

    candidate_signals = [
        "first name",
        "firstname",
        "last name",
        "lastname",
        "full name",
        "email",
        "phone",
        "mobile",
        "telephone",
        "address",
        "city",
        "state",
        "country",
        "postal",
        "zip",
        "resume",
        "cv",
        "cover letter",
        "linkedin",
        "github",
        "portfolio",
        "website",
        "work authorization",
        "authorization",
        "sponsorship",
        "education",
        "school",
        "university",
        "degree",
        "experience",
        "employment",
    ]

    return any(
        signal in combined
        for signal in candidate_signals
    )


async def _get_label(page, element):
    """
    Resolve the most useful human-readable label.

    Priority:
    1. <label for="...">
    2. Ancestor <label>
    3. aria-label
    """

    try:
        element_id = await element.get_attribute(
            "id"
        )

        if element_id:
            label = page.locator(
                f'label[for="{element_id}"]'
            ).first

            if await label.count():
                text = await label.inner_text()

                if _clean(text):
                    return _clean(text)

    except Exception:
        pass

    try:
        parent_label = element.locator(
            "xpath=ancestor::label[1]"
        )

        if await parent_label.count():
            text = await parent_label.inner_text()

            if _clean(text):
                return _clean(text)

    except Exception:
        pass

    try:
        aria_label = await element.get_attribute(
            "aria-label"
        )

        if _clean(aria_label):
            return _clean(aria_label)

    except Exception:
        pass

    return ""


async def _get_select_options(element):
    """
    Extract options from a native <select>.
    """

    options = []

    try:
        option_elements = element.locator(
            "option"
        )

        for i in range(
            await option_elements.count()
        ):
            option = option_elements.nth(i)

            try:
                text = _clean(
                    await option.inner_text()
                )

                value = _clean(
                    await option.get_attribute(
                        "value"
                    )
                )

                disabled = (
                    await option.get_attribute(
                        "disabled"
                    )
                ) is not None

                selected = (
                    await option.get_attribute(
                        "selected"
                    )
                ) is not None

                if not text and not value:
                    continue

                options.append(
                    {
                        "text": text,
                        "value": value,
                        "disabled": disabled,
                        "selected": selected,
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


async def _get_datalist_options(
    page,
    element,
):
    """
    Extract options from a datalist associated
    with an input.
    """

    options = []

    try:
        list_id = await element.get_attribute(
            "list"
        )

        if not list_id:
            return options

        datalist = page.locator(
            f'datalist#"{list_id}"'
        )

        if await datalist.count() == 0:
            datalist = page.locator(
                f'datalist#{list_id}'
            )

        if await datalist.count() == 0:
            return options

        option_elements = datalist.locator(
            "option"
        )

        for i in range(
            await option_elements.count()
        ):
            option = option_elements.nth(i)

            try:
                text = _clean(
                    await option.inner_text()
                )

                value = _clean(
                    await option.get_attribute(
                        "value"
                    )
                )

                label = _clean(
                    await option.get_attribute(
                        "label"
                    )
                )

                display = (
                    text
                    or label
                    or value
                )

                if not display:
                    continue

                options.append(
                    {
                        "text": display,
                        "value": value,
                        "disabled": False,
                        "selected": False,
                        "source": "datalist",
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


async def _get_aria_options(page, element):
    """
    Inspect only an ARIA listbox that is explicitly
    associated with this particular control.

    Important:
    Do NOT search the entire page for a random listbox.
    Many ATS pages contain hidden/global listboxes.
    """

    options = []

    try:
        role = (
            await element.get_attribute("role")
            or ""
        ).lower()

        aria_haspopup = (
            await element.get_attribute(
                "aria-haspopup"
            )
            or ""
        ).lower()

        aria_controls = _clean(
            await element.get_attribute(
                "aria-controls"
            )
        )

        aria_owns = _clean(
            await element.get_attribute(
                "aria-owns"
            )
        )

        is_combobox = (
            role == "combobox"
            or aria_haspopup == "listbox"
            or bool(aria_controls)
            or bool(aria_owns)
        )

        if not is_combobox:
            return options

        listbox = None

        # Only use an explicitly referenced listbox.
        if aria_controls:
            candidate = page.locator(
                f"#{aria_controls}"
            ).first

            if await candidate.count() > 0:
                listbox = candidate

        if (
            listbox is None
            and aria_owns
        ):
            candidate = page.locator(
                f"#{aria_owns}"
            ).first

            if await candidate.count() > 0:
                listbox = candidate

        # IMPORTANT:
        # Do not fall back to:
        #
        # page.locator('[role="listbox"]').last
        #
        # because that can associate another field's
        # dropdown with this field.

        if listbox is None:
            return options

        option_elements = listbox.locator(
            '[role="option"]'
        )

        for i in range(
            await option_elements.count()
        ):
            option = option_elements.nth(i)

            try:
                text = _clean(
                    await option.inner_text()
                )

                value = _clean(
                    await option.get_attribute(
                        "data-value"
                    )
                )

                if not value:
                    value = _clean(
                        await option.get_attribute(
                            "value"
                        )
                    )

                if not text and not value:
                    continue

                disabled = (
                    (
                        await option.get_attribute(
                            "aria-disabled"
                        )
                    )
                    or ""
                ).lower() == "true"

                selected = (
                    (
                        await option.get_attribute(
                            "aria-selected"
                        )
                    )
                    or ""
                ).lower() == "true"

                options.append(
                    {
                        "text": text,
                        "value": value,
                        "disabled": disabled,
                        "selected": selected,
                        "source": "aria",
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


async def _get_nearby_choice_options(page, element):
    """
    Detect genuine radio/checkbox choices associated
    with the field.

    Do not treat arbitrary buttons inside an ATS
    container as field options.
    """

    options = []

    try:
        container = element.locator(
            "xpath="
            "ancestor::*["
            "self::fieldset "
            "or @role='radiogroup'"
            "][1]"
        )

        if await container.count() == 0:
            return options

        controls = container.locator(
            "input[type='radio'], "
            "input[type='checkbox'], "
            "[role='radio']"
        )

        for i in range(
            await controls.count()
        ):
            control = controls.nth(i)

            try:
                control_type = _clean(
                    await control.get_attribute(
                        "type"
                    )
                ).lower()

                role = _clean(
                    await control.get_attribute(
                        "role"
                    )
                ).lower()

                control_id = _clean(
                    await control.get_attribute(
                        "id"
                    )
                )

                value = _clean(
                    await control.get_attribute(
                        "value"
                    )
                )

                aria_label = _clean(
                    await control.get_attribute(
                        "aria-label"
                    )
                )

                text = ""

                try:
                    text = _clean(
                        await control.inner_text()
                    )
                except Exception:
                    pass

                if not text and control_id:
                    try:
                        label = page.locator(
                            f'label[for="{control_id}"]'
                        ).first

                        if await label.count():
                            text = _clean(
                                await label.inner_text()
                            )
                    except Exception:
                        pass

                display = (
                    text
                    or aria_label
                    or value
                )

                if not display:
                    continue

                if (
                    control_type
                    not in {
                        "radio",
                        "checkbox",
                    }
                    and role != "radio"
                ):
                    continue

                disabled = (
                    await control.get_attribute(
                        "disabled"
                    )
                ) is not None

                aria_disabled = (
                    (
                        await control.get_attribute(
                            "aria-disabled"
                        )
                    )
                    or ""
                ).lower() == "true"

                selected = (
                    await control.get_attribute(
                        "checked"
                    )
                ) is not None

                if (
                    (
                        await control.get_attribute(
                            "aria-checked"
                        )
                    )
                    or ""
                ).lower() == "true":
                    selected = True

                options.append(
                    {
                        "text": display,
                        "value": value,
                        "disabled": (
                            disabled
                            or aria_disabled
                        ),
                        "selected": selected,
                        "source": "nearby_control",
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


def _deduplicate_options(options):
    """
    Remove duplicate option representations while
    preserving the first occurrence.
    """

    unique = []
    seen = set()

    for option in options:
        if not isinstance(option, dict):
            continue

        text = _clean(
            option.get("text")
        )

        value = _clean(
            option.get("value")
        )

        key = (
            text.lower(),
            value.lower(),
        )

        if not text and not value:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique.append(option)

    return unique


async def _inspect_field(page, element):
    try:
        field_type = (
            await element.get_attribute(
                "type"
            )
            or "text"
        )

        name = (
            await element.get_attribute("name")
            or ""
        )

        field_id = (
            await element.get_attribute("id")
            or ""
        )

        placeholder = (
            await element.get_attribute(
                "placeholder"
            )
            or ""
        )

        required = (
            await element.get_attribute(
                "required"
            )
        ) is not None

        aria_required = (
            await element.get_attribute(
                "aria-required"
            )
            or ""
        ).lower()

        if aria_required == "true":
            required = True

        aria_label = (
            await element.get_attribute(
                "aria-label"
            )
            or ""
        )

        autocomplete = (
            await element.get_attribute(
                "autocomplete"
            )
            or ""
        )

        automation_id = (
            await element.get_attribute(
                "data-automation-id"
            )
            or ""
        )

        qa = (
            await element.get_attribute(
                "data-qa"
            )
            or ""
        )

        # New control metadata.
        role = (
            await element.get_attribute(
                "role"
            )
            or ""
        )

        aria_haspopup = (
            await element.get_attribute(
                "aria-haspopup"
            )
            or ""
        )

        aria_expanded = (
            await element.get_attribute(
                "aria-expanded"
            )
            or ""
        )

        aria_autocomplete = (
            await element.get_attribute(
                "aria-autocomplete"
            )
            or ""
        )

        aria_controls = (
            await element.get_attribute(
                "aria-controls"
            )
            or ""
        )

        aria_owns = (
            await element.get_attribute(
                "aria-owns"
            )
            or ""
        )

        list_attribute = (
            await element.get_attribute(
                "list"
            )
            or ""
        )

        label = await _get_label(
            page,
            element,
        )

        tag = await element.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

        field = {
            "tag": _clean(tag),
            "type": _clean(field_type),
            "name": _clean(name),
            "id": _clean(field_id),
            "label": _clean(label),
            "placeholder": _clean(
                placeholder
            ),
            "aria_label": _clean(
                aria_label
            ),
            "autocomplete": _clean(
                autocomplete
            ),
            "automation_id": _clean(
                automation_id
            ),
            "qa": _clean(qa),
            "required": required,

            # Rich control metadata.
            "role": _clean(role),
            "aria_haspopup": _clean(
                aria_haspopup
            ),
            "aria_expanded": _clean(
                aria_expanded
            ),
            "aria_autocomplete": _clean(
                aria_autocomplete
            ),
            "aria_controls": _clean(
                aria_controls
            ),
            "aria_owns": _clean(
                aria_owns
            ),
        }

        options = []

        # -----------------------------------------------------
        # Native SELECT
        # -----------------------------------------------------

        if tag == "select":
            field["multiple"] = (
                await element.get_attribute(
                    "multiple"
                )
            ) is not None

            options.extend(
                await _get_select_options(
                    element
                )
            )

        # -----------------------------------------------------
        # Datalist
        # -----------------------------------------------------

        if list_attribute:
            options.extend(
                await _get_datalist_options(
                    page,
                    element,
                )
            )

        # -----------------------------------------------------
        # ARIA combobox/listbox
        # -----------------------------------------------------

        options.extend(
            await _get_aria_options(
                page,
                element,
            )
        )

        # -----------------------------------------------------
        # Nearby radio/choice controls
        # -----------------------------------------------------

        options.extend(
            await _get_nearby_choice_options(
                page,
                element,
            )
        )

        options = _deduplicate_options(
            options
        )

        if options:
            field["options"] = options

        # Determine whether this appears to be a
        # choice/combobox field even when the native
        # input type is "text".
        field["control_kind"] = (
            "choice"
            if (
                options
                or role.lower() == "combobox"
                or aria_haspopup.lower()
                == "listbox"
                or aria_autocomplete
            )
            else "text"
        )

        return field

    except Exception:
        return None


async def _find_application_links(
    page,
    base_url,
):
    results = []

    links = page.locator("a")

    for i in range(
        await links.count()
    ):
        element = links.nth(i)

        try:
            text = _clean(
                await element.inner_text()
            )

            href = _clean(
                await element.get_attribute(
                    "href"
                )
            )

            if not href:
                continue

            combined = (
                f"{text} {href}"
            ).lower()

            if not _contains_signal(
                combined,
                APPLICATION_LINK_SIGNALS,
            ):
                continue

            absolute_url = urljoin(
                base_url,
                href,
            )

            parsed = urlparse(
                absolute_url
            )

            if parsed.scheme not in {
                "http",
                "https",
            }:
                continue

            results.append(
                {
                    "text": text,
                    "href": absolute_url,
                    "source": "link",
                }
            )

        except Exception:
            continue

    unique = []
    seen = set()

    for item in results:
        key = item["href"]

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


async def _find_application_attributes(
    page,
    base_url,
):
    results = []

    elements = page.locator("*")

    for i in range(
        await elements.count()
    ):
        element = elements.nth(i)

        try:
            attributes = await element.evaluate(
                """
                el => Array.from(el.attributes).map(
                    a => [a.name, a.value]
                )
                """
            )

            for name, value in attributes:
                value = _clean(value)

                if not value:
                    continue

                name_lower = name.lower()
                value_lower = value.lower()

                combined = (
                    f"{name_lower} "
                    f"{value_lower}"
                )

                if not _contains_signal(
                    combined,
                    APPLICATION_LINK_SIGNALS,
                ):
                    continue

                if not (
                    "url" in name_lower
                    or "href" in name_lower
                    or "link" in name_lower
                    or "apply" in name_lower
                ):
                    continue

                if not value.startswith(
                    (
                        "http://",
                        "https://",
                        "/",
                    )
                ):
                    continue

                absolute_url = urljoin(
                    base_url,
                    value,
                )

                parsed = urlparse(
                    absolute_url
                )

                if parsed.scheme not in {
                    "http",
                    "https",
                }:
                    continue

                results.append(
                    {
                        "attribute": name,
                        "href": absolute_url,
                        "source": "attribute",
                    }
                )

        except Exception:
            continue

    unique = []
    seen = set()

    for item in results:
        key = item["href"]

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


async def _inspect_page(page, url):
    title = _clean(
        await page.title()
    )

    body_text = ""

    try:
        body_text = _clean(
            await page.locator(
                "body"
            ).inner_text()
        )

    except Exception:
        pass

    body_lower = body_text.lower()
    title_lower = title.lower()

    application_signals = []

    for signal in APPLICATION_SIGNALS:
        if (
            signal in body_lower
            or signal in title_lower
        ):
            application_signals.append(
                signal
            )

    forms = page.locator("form")

    form_count = await forms.count()

    all_fields = []

    # Hidden fields deliberately excluded.
    inputs = page.locator(
        "input:not([type='hidden']):not([disabled])"
    )

    for i in range(
        await inputs.count()
    ):
        field = await _inspect_field(
            page,
            inputs.nth(i),
        )

        if field:
            all_fields.append(field)

    textareas = page.locator(
        "textarea:not([disabled])"
    )

    for i in range(
        await textareas.count()
    ):
        field = await _inspect_field(
            page,
            textareas.nth(i),
        )

        if field:
            all_fields.append(field)

    selects = page.locator(
        "select:not([disabled])"
    )

    for i in range(
        await selects.count()
    ):
        field = await _inspect_field(
            page,
            selects.nth(i),
        )

        if field:
            all_fields.append(field)

    candidate_fields = [
        field
        for field in all_fields
        if _looks_like_candidate_field(
            field
        )
    ]

    submit_count = await page.locator(
        "button[type='submit'], "
        "input[type='submit']"
    ).count()

    application_links = (
        await _find_application_links(
            page,
            url,
        )
    )

    application_attributes = (
        await _find_application_attributes(
            page,
            url,
        )
    )

    application_urls = []

    for item in (
        application_links
        + application_attributes
    ):
        href = item.get("href")

        if (
            href
            and href not in application_urls
        ):
            application_urls.append(
                href
            )

    is_application_form = (
        len(candidate_fields) > 0
        and (
            form_count > 0
            or submit_count > 0
            or len(application_signals) >= 2
        )
    )

    return {
        "title": title,
        "form_count": form_count,
        "field_count": len(all_fields),
        "candidate_field_count": (
            len(candidate_fields)
        ),
        "ignored_field_count": (
            len(all_fields)
            - len(candidate_fields)
        ),
        "submit_control_count": (
            submit_count
        ),
        "application_signals": (
            application_signals
        ),
        "application_links": (
            application_links
        ),
        "application_attributes": (
            application_attributes
        ),
        "application_urls": (
            application_urls
        ),
        "fields": candidate_fields,
        "is_application_form": (
            is_application_form
        ),
    }


async def inspect_application_form(url):
    """
    Inspect a job/application page.

    Strictly read-only.

    It:
        - opens the supplied URL
        - follows normal redirects
        - detects application forms
        - detects candidate fields
        - detects application destinations
        - extracts field metadata
        - extracts available choice options

    It NEVER:
        - fills a field
        - uploads a file
        - checks a consent checkbox
        - clicks submit
        - submits an application
    """

    if (
        not isinstance(url, str)
        or not url.strip()
    ):
        return {
            "status": "error",
            "message": (
                "Application URL is required."
            ),
        }

    url = url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return {
            "status": "error",
            "message": (
                "Only HTTP/HTTPS URLs "
                "are supported."
            ),
        }

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
                try:
                    await page.wait_for_timeout(
                        3000
                    )

                    if (
                        await page.locator(
                            "body"
                        ).count()
                        == 0
                    ):
                        await browser.close()

                        return {
                            "status": "timeout",
                            "is_application_form": False,
                            "url": url,
                            "application_url": None,
                            "message": (
                                "Application page timed "
                                "out before usable page "
                                "content was available."
                            ),
                        }

                except Exception:
                    await browser.close()

                    return {
                        "status": "timeout",
                        "is_application_form": False,
                        "url": url,
                        "application_url": None,
                        "message": (
                            "Application page timed "
                            "out while loading."
                        ),
                    }

                response = None

            result = await _inspect_page(
                page,
                url,
            )

            application_url = None

            if result["application_urls"]:
                application_url = (
                    result[
                        "application_urls"
                    ][0]
                )

            if result[
                "is_application_form"
            ]:
                reason = (
                    "Candidate application fields "
                    "were detected on the page."
                )

            elif application_url:
                reason = (
                    "An application destination "
                    "was detected on the page."
                )

            else:
                reason = (
                    "No application form or "
                    "application destination "
                    "was discoverable."
                )

            output = {
                "status": "success",
                "is_application_form": (
                    result[
                        "is_application_form"
                    ]
                ),
                "url": url,
                "final_url": page.url,
                "title": result["title"],
                "http_status": (
                    response.status
                    if response
                    else None
                ),
                "application_url": (
                    application_url
                ),
                "application_source": (
                    result[
                        "application_links"
                    ][0]
                    if result[
                        "application_links"
                    ]
                    else (
                        result[
                            "application_attributes"
                        ][0]
                        if result[
                            "application_attributes"
                        ]
                        else None
                    )
                ),
                "reason": reason,
                "form_count": (
                    result["form_count"]
                ),
                "field_count": (
                    result["field_count"]
                ),
                "candidate_field_count": (
                    result[
                        "candidate_field_count"
                    ]
                ),
                "ignored_field_count": (
                    result[
                        "ignored_field_count"
                    ]
                ),
                "submit_control_count": (
                    result[
                        "submit_control_count"
                    ]
                ),
                "application_signals": (
                    result[
                        "application_signals"
                    ]
                ),
                "application_urls": (
                    result[
                        "application_urls"
                    ]
                ),
                "fields": result["fields"],
            }

            await browser.close()

            return output

    except Exception as exc:
        return {
            "status": "error",
            "is_application_form": False,
            "url": url,
            "application_url": None,
            "message": str(exc),
        }


def inspect_application_form_sync(url):
    return asyncio.run(
        inspect_application_form(url)
    )