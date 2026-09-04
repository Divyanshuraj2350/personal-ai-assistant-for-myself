import re


MAX_CONTENT_LENGTH = 4000


def clean_text(text):
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove common navigation noise
    noise_patterns = [
        r"\bhome\b",
        r"\bmenu\b",
        r"\blogin\b",
        r"\bsign up\b",
        r"\bsubscribe\b",
        r"\bcookie policy\b",
        r"\bprivacy policy\b",
        r"\bterms of service\b",
    ]

    for pattern in noise_patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    # Clean whitespace again after removing noise
    text = re.sub(r"\s+", " ", text).strip()

    return text


def clean_result(result):
    title = result.get("title", "").strip()
    url = result.get("url", "").strip()
    content = result.get("content", "")

    content = clean_text(content)

    # Prevent extremely large pages from reaching the LLM
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "..."

    return {
        "title": title,
        "url": url,
        "content": content,
        "relevance_score": result.get("relevance_score"),
    }


def clean_results(results):
    return [
        clean_result(result)
        for result in results
    ]