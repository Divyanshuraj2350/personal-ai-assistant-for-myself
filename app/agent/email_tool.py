import re
import uuid
import json
import httpx


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"

EMAIL_PATTERN = r"[\w\.-]+@[\w\.-]+\.\w+"


def extract_email_address(message):
    match = re.search(EMAIL_PATTERN, message)

    if not match:
        return None

    return match.group(0)


async def generate_email_draft(message):

    recipient = extract_email_address(message)

    if not recipient:
        return {
            "status": "error",
            "error": "No email address found.",
        }

    prompt = f"""
Create an email based on the user's instruction below.

User instruction:
{message}

Return ONLY valid JSON in this exact format:

{{
    "subject": "email subject",
    "body": "complete email body"
}}

Rules:
- Write a professional and natural email.
- Understand the user's intent before writing.
- Do not invent important facts.
- Make the email complete.
- Do not include explanations outside the JSON.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an email drafting assistant. "
                    "Generate complete, professional emails."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0.3,
        },
    }

    async with httpx.AsyncClient(timeout=None) as client:

        response = await client.post(
            OLLAMA_URL,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    content = data.get("message", {}).get("content", "")

    if not content:
        return {
            "status": "error",
            "error": "Qwen returned an empty response.",
        }

    try:

        draft = json.loads(content)

    except json.JSONDecodeError:

        return {
            "status": "error",
            "error": "Qwen returned invalid JSON.",
            "raw": content,
        }

    subject = draft.get("subject", "").strip()
    body = draft.get("body", "").strip()

    if not subject or not body:

        return {
            "status": "error",
            "error": "Generated email is incomplete.",
        }

    # Create a unique ID for this approval request
    approval_id = str(uuid.uuid4())

    return {
        "status": "draft",
        "approval_id": approval_id,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "requires_approval": True,
    }