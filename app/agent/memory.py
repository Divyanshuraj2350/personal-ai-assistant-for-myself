import json
import os
import re
import uuid
from datetime import datetime


# ============================================================
# SHORT-TERM CONVERSATION MEMORY
# ============================================================
#
# Session memory is persistent.
#
# Each session is stored separately:
#
# data/sessions/
#     session-a.json
#     session-b.json
#
# This allows conversation context to survive server restarts
# while keeping different sessions isolated.
#
# ============================================================

MAX_MESSAGES = 12

SESSION_DIRECTORY = "data/sessions"


def _ensure_session_directory():
    """
    Create the session storage directory if it does not exist.
    """

    os.makedirs(
        SESSION_DIRECTORY,
        exist_ok=True,
    )


def _safe_session_id(session_id):
    """
    Convert a session ID into a safe filename.

    This prevents path traversal and unsafe filenames.
    """

    if not isinstance(
        session_id,
        str,
    ):
        session_id = "default"

    session_id = session_id.strip()

    if not session_id:
        session_id = "default"

    safe_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        session_id,
    )

    return safe_id


def _get_session_file(session_id):
    """
    Return the JSON file path for a session.
    """

    _ensure_session_directory()

    safe_id = _safe_session_id(
        session_id
    )

    return os.path.join(
        SESSION_DIRECTORY,
        f"{safe_id}.json",
    )


def _load_session(session_id):
    """
    Load conversation history for one session.

    Returns an empty list if the session does not exist
    or cannot be read.
    """

    session_file = _get_session_file(
        session_id
    )

    if not os.path.exists(
        session_file
    ):
        return []

    try:

        with open(
            session_file,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            list,
        ):
            return []

        valid_messages = []

        for message in data:

            if not isinstance(
                message,
                dict,
            ):
                continue

            role = message.get(
                "role"
            )

            content = message.get(
                "content"
            )

            if (
                role in (
                    "user",
                    "assistant",
                    "system",
                )
                and isinstance(
                    content,
                    str,
                )
                and content.strip()
            ):

                valid_messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        return valid_messages

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []


def _save_session(
    session_id,
    history,
):
    """
    Persist conversation history for one session.
    """

    session_file = _get_session_file(
        session_id
    )

    try:

        with open(
            session_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                history,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return True

    except OSError:

        return False


def get_history(session_id):
    """
    Return recent conversation history for a session.

    History is loaded from persistent storage, so it
    survives server restarts.
    """

    history = _load_session(
        session_id
    )

    if len(history) > MAX_MESSAGES:

        history = history[
            -MAX_MESSAGES:
        ]

    return history


def add_message(
    session_id,
    role,
    content,
):
    """
    Add a message to persistent conversation history.

    Only the most recent MAX_MESSAGES messages are kept.
    """

    if role not in (
        "user",
        "assistant",
        "system",
    ):
        return False

    if not isinstance(
        content,
        str,
    ):
        return False

    content = content.strip()

    if not content:
        return False

    history = _load_session(
        session_id
    )

    history.append(
        {
            "role": role,
            "content": content,
        }
    )

    if len(history) > MAX_MESSAGES:

        history = history[
            -MAX_MESSAGES:
        ]

    return _save_session(
        session_id,
        history,
    )


def delete_session(
    session_id,
):
    """
    Delete one session and all of its stored conversation
    history.
    """

    session_file = _get_session_file(
        session_id
    )

    if not os.path.exists(
        session_file
    ):
        return False

    try:

        os.remove(
            session_file
        )

        return True

    except OSError:

        return False


# ============================================================
# LONG-TERM MEMORY
# ============================================================

MEMORY_FILE = "data/personal_memory.json"


def _ensure_memory_file():
    """
    Create the memory file if it does not exist.
    """

    directory = os.path.dirname(
        MEMORY_FILE
    )

    if directory:

        os.makedirs(
            directory,
            exist_ok=True,
        )

    if not os.path.exists(
        MEMORY_FILE
    ):

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                [],
                file,
                indent=2,
                ensure_ascii=False,
            )


def _load_memories():
    """
    Load persistent long-term memories from disk.
    """

    _ensure_memory_file()

    try:

        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            list,
        ):
            return []

        return data

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []


def _save_memories(
    memories,
):
    """
    Persist long-term memories to disk.
    """

    _ensure_memory_file()

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            memories,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# SAVE LONG-TERM MEMORY
# ============================================================

def save_memory(
    content,
    category="general",
):
    """
    Save a useful long-term personal memory.

    This function stores explicit information.
    It does not automatically decide whether
    something should be remembered.
    """

    if not isinstance(
        content,
        str,
    ):
        return None

    content = content.strip()

    if not content:
        return None

    memories = _load_memories()

    # Prevent exact duplicates.
    for memory in memories:

        existing_content = str(
            memory.get(
                "content",
                "",
            )
        ).strip().lower()

        if (
            existing_content
            == content.lower()
        ):

            return memory

    memory = {
        "id": str(
            uuid.uuid4()
        ),
        "content": content,
        "category": category,
        "created_at": datetime.now().isoformat(),
    }

    memories.append(
        memory
    )

    _save_memories(
        memories
    )

    return memory


# ============================================================
# MEMORY DETECTION
# ============================================================

MEMORY_TRIGGERS = [
    "remember that",
    "remember this",
    "don't forget",
    "do not forget",
    "from now on",
    "keep in mind",
    "my preference is",
    "my preference:",
]


def detect_memory_request(message):
    """
    Detect whether the user explicitly wants
    something remembered.

    Returns:
        {
            "should_remember": bool,
            "content": str | None,
            "category": str
        }

    This is intentionally rule-based for the
    first Personal AI memory phase.
    """

    if not isinstance(
        message,
        str,
    ):

        return {
            "should_remember": False,
            "content": None,
            "category": "general",
        }

    text = message.strip()

    if not text:

        return {
            "should_remember": False,
            "content": None,
            "category": "general",
        }

    lowered = text.lower()

    matched_trigger = None

    for trigger in MEMORY_TRIGGERS:

        if lowered.startswith(
            trigger
        ):

            matched_trigger = trigger
            break

    if matched_trigger is None:

        return {
            "should_remember": False,
            "content": None,
            "category": "general",
        }

    content = text[
        len(matched_trigger):
    ].strip(
        " \t:,-"
    )

    if not content:

        return {
            "should_remember": False,
            "content": None,
            "category": "general",
        }

    category = "general"

    lowered_content = content.lower()

    if (
        "project"
        in lowered_content
    ):

        category = "project"

    elif (
        "prefer"
        in lowered_content
        or "preference"
        in lowered_content
        or "favorite"
        in lowered_content
    ):

        category = "preference"

    elif (
        "goal"
        in lowered_content
    ):

        category = "goal"

    elif (
        "work"
        in lowered_content
        or "career"
        in lowered_content
        or "job"
        in lowered_content
    ):

        category = "career"

    return {
        "should_remember": True,
        "content": content,
        "category": category,
    }


def remember_if_requested(
    message,
):
    """
    Save a memory only when the user explicitly
    asks the assistant to remember something.
    """

    decision = detect_memory_request(
        message
    )

    if not decision[
        "should_remember"
    ]:

        return None

    return save_memory(
        decision[
            "content"
        ],
        decision[
            "category"
        ],
    )


# ============================================================
# GET ALL LONG-TERM MEMORIES
# ============================================================

def get_memories(
    category=None,
):
    """
    Return stored long-term memories.

    If category is provided, only memories
    from that category are returned.
    """

    memories = _load_memories()

    if category is None:

        return memories

    return [
        memory
        for memory in memories
        if memory.get(
            "category"
        ) == category
    ]


# ============================================================
# SEARCH LONG-TERM MEMORIES
# ============================================================

MEMORY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "about",
    "be",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "say",
    "should",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def search_memories(
    query,
    limit=5,
):
    """
    Return long-term memories that share meaningful words
    with the user's request.
    """

    if not isinstance(query, str):
        return []

    query_words = {
        word
        for word in re.findall(
            r"\b\w+\b",
            query.lower(),
        )
        if len(word) >= 3
        and word not in MEMORY_STOP_WORDS
    }

    if not query_words:
        return []

    scored = []

    for memory in _load_memories():
        content = str(
            memory.get(
                "content",
                "",
            )
        ).lower()

        content_words = set(
            re.findall(
                r"\b\w+\b",
                content,
            )
        )

        score = len(
            query_words.intersection(
                content_words
            )
        )

        if score > 0:
            scored.append(
                (
                    score,
                    memory,
                )
            )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].get(
                "created_at",
                "",
            ),
        ),
        reverse=True,
    )

    return [
        memory
        for score, memory in scored[:limit]
    ]

# ============================================================
# DELETE LONG-TERM MEMORY
# ============================================================

def delete_memory(
    memory_id,
):
    """
    Delete one long-term memory by ID.
    """

    memories = _load_memories()

    updated = [
        memory
        for memory in memories
        if memory.get(
            "id"
        ) != memory_id
    ]

    if len(updated) == len(
        memories
    ):

        return False

    _save_memories(
        updated
    )

    return True