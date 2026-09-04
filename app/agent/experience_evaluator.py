import re
from datetime import date, datetime


def parse_required_years(requirements):
    """
    Extract the minimum experience requirement
    from job experience text.

    Examples:
        "2+ years of experience" -> 2.0
        "3 years experience" -> 3.0
        "1-2 years" -> 1.0
    """

    if not requirements:
        return None

    text = " ".join(
        str(item)
        for item in requirements
    ).lower()

    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+\s*years?",
        r"(\d+(?:\.\d+)?)\s*-\s*\d+(?:\.\d+)?\s*years?",
        r"(\d+(?:\.\d+)?)\s*years?",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:
            return float(
                match.group(1)
            )

    return None


def parse_date(value):
    """
    Convert common profile date formats
    into a Python date.
    """

    if not value:
        return None

    value = str(value).strip()

    formats = [
        "%b %Y",
        "%B %Y",
        "%Y-%m",
        "%Y/%m",
        "%Y",
    ]

    for fmt in formats:

        try:

            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.date()

        except ValueError:
            continue

    return None


def calculate_experience_months(
    experience_entries,
):
    """
    Calculate total professional experience
    from profile experience entries.

    Overlapping periods are not double-counted.
    """

    periods = []

    for entry in experience_entries:

        start = parse_date(
            entry.get("start_date")
        )

        end = parse_date(
            entry.get("end_date")
        )

        if not start:
            continue

        if not end:
            end = date.today()

        if end < start:
            continue

        periods.append(
            (
                start,
                end,
            )
        )

    if not periods:
        return 0

    periods.sort(
        key=lambda period: period[0]
    )

    merged = []

    current_start, current_end = periods[0]

    for start, end in periods[1:]:

        if start <= current_end:

            if end > current_end:
                current_end = end

        else:

            merged.append(
                (
                    current_start,
                    current_end,
                )
            )

            current_start = start
            current_end = end

    merged.append(
        (
            current_start,
            current_end,
        )
    )

    total_months = 0

    for start, end in merged:

        months = (
            (end.year - start.year) * 12
            + (end.month - start.month)
        )

        if end.day >= start.day:
            months += 1

        total_months += months

    return total_months


def evaluate_experience(
    profile,
    job,
):
    """
    Compare the candidate's recorded experience
    against the job's stated experience requirement.
    """

    requirements = job.get(
        "experience",
        [],
    )

    profile_experience = profile.get(
        "experience",
        [],
    )

    required_years = parse_required_years(
        requirements
    )

    # --------------------------------------------------
    # No requirement specified
    # --------------------------------------------------

    if required_years is None:

        return {
            "status": "not_specified",
            "required_years": None,
            "candidate_years": round(
                calculate_experience_months(
                    profile_experience
                ) / 12,
                2,
            ),
            "required": requirements,
            "message": (
                "The job does not specify "
                "a clear minimum number of years."
            ),
        }

    # --------------------------------------------------
    # Calculate candidate experience
    # --------------------------------------------------

    candidate_months = (
        calculate_experience_months(
            profile_experience
        )
    )

    candidate_years = round(
        candidate_months / 12,
        2,
    )

    # --------------------------------------------------
    # Compare experience
    # --------------------------------------------------

    required_months = (
        required_years * 12
    )

    if candidate_months >= required_months:

        status = "met"

        message = (
            "The candidate meets the "
            "stated experience requirement."
        )

    elif candidate_months >= (
        required_months * 0.5
    ):

        status = "partially_met"

        message = (
            "The candidate has relevant "
            "experience but does not fully "
            "meet the stated requirement."
        )

    else:

        status = "not_met"

        message = (
            "The candidate does not currently "
            "meet the stated minimum experience "
            "requirement."
        )

    return {
        "status": status,
        "required_years": required_years,
        "candidate_years": candidate_years,
        "candidate_months": candidate_months,
        "required": requirements,
        "profile": profile_experience,
        "message": message,
    }
