import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

PROFILE_PATH = BASE_DIR / "data" / "career_profile.json"


def load_profile():
    """
    Load the user's career profile from disk.
    """

    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"Career profile not found: {PROFILE_PATH}"
        )

    with open(
        PROFILE_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def save_profile(profile):
    """
    Save the complete career profile to disk.
    """

    PROFILE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        PROFILE_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            profile,
            file,
            indent=4,
            ensure_ascii=False,
        )


def get_profile():
    """
    Return the current career profile.
    """

    return load_profile()


def update_profile(section, data):
    """
    Update one top-level section of the career profile.

    Example:

        update_profile(
            "skills",
            {
                "programming_languages": [
                    "Python",
                    "Java"
                ]
            }
        )
    """

    profile = load_profile()

    if section not in profile:
        raise ValueError(
            f"Unknown profile section: {section}"
        )

    profile[section] = data

    save_profile(profile)

    return profile