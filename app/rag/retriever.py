import re

from app.rag.store import (
    search_documents,
    get_document_chunks,
)


RELEVANCE_THRESHOLD = 1.25

# Retrieve more candidates before final ranking.
CANDIDATE_LIMIT = 30

# Maximum number of final chunks normally returned.
FINAL_RESULT_LIMIT = 5

# Number of neighboring chunks to include around a strong match.
NEIGHBOR_WINDOW = 1


def _normalize_text(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)

    return text.strip()


def _extract_query_terms(query):
    normalized = _normalize_text(query)

    if not normalized:
        return []

    stop_words = {
        "what",
        "is",
        "the",
        "a",
        "an",
        "are",
        "was",
        "were",
        "when",
        "where",
        "who",
        "how",
        "why",
        "which",
        "does",
        "do",
        "did",
        "my",
        "me",
        "i",
        "of",
        "for",
        "to",
        "in",
        "on",
        "and",
        "or",
        "from",
        "about",
        "tell",
        "can",
        "you",
        "please",
        "give",
        "time",
        "date",
    }

    terms = []

    for term in normalized.split():
        if term in stop_words:
            continue

        if len(term) < 3:
            continue

        if term not in terms:
            terms.append(term)

    return terms


def _keyword_match_score(query, content):
    query_terms = _extract_query_terms(query)

    if not query_terms:
        return 0.0

    normalized_content = _normalize_text(content)

    if not normalized_content:
        return 0.0

    content_words = set(normalized_content.split())

    matched_terms = 0

    for term in query_terms:
        if term in content_words:
            matched_terms += 1

    return matched_terms / len(query_terms)


def _calculate_retrieval_score(distance, keyword_score):
    if distance is None:
        return float("-inf")

    semantic_score = RELEVANCE_THRESHOLD - distance
    keyword_bonus = keyword_score * 0.75

    return semantic_score + keyword_bonus


def _is_relevant_candidate(distance, keyword_score):
    """
    A candidate is relevant when either:
    - semantic similarity passes the normal threshold, OR
    - enough important query terms appear in the chunk.
    """
    semantic_match = (
        distance is not None
        and distance <= RELEVANCE_THRESHOLD
    )

    strong_keyword_match = keyword_score >= 0.5

    return semantic_match or strong_keyword_match


def _expand_document_context(ranked_results):
    """
    Expand strong document matches with all chunks belonging
    to the same document.

    This is useful when OCR/table extraction separates related
    information across multiple chunks.
    """

    if not ranked_results:
        return ranked_results

    expanded = []
    expanded_documents = set()

    for result in ranked_results:

        metadata = result.get("metadata") or {}
        document_id = metadata.get("document_id")

        if not document_id:
            expanded.append(result)
            continue

        # Expand a document when a retrieved result is relevant.
        if document_id not in expanded_documents:

            document_chunks = get_document_chunks(
                document_id
            )

            if document_chunks:

                for chunk in document_chunks:

                    chunk_metadata = (
                        chunk.get("metadata") or {}
                    )

                    expanded.append(
                        {
                            "content": chunk.get(
                                "content",
                                "",
                            ),
                            "metadata": chunk_metadata,
                            "distance": result.get(
                                "distance"
                            ),
                            "keyword_score": result.get(
                                "keyword_score",
                                0.0,
                            ),
                            "retrieval_score": result.get(
                                "retrieval_score",
                                0.0,
                            ),
                            "context_expanded": True,
                        }
                    )

                expanded_documents.add(document_id)

            else:
                expanded.append(result)

        else:
            # Don't duplicate chunks from the same document.
            continue

    return expanded


def retrieve_relevant_knowledge(
    query,
    limit=FINAL_RESULT_LIMIT,
):
    """
    Retrieve relevant knowledge using:
    1. semantic similarity
    2. keyword matching
    3. document-aware context expansion

    This common path works for:
    - documents
    - scanned PDFs
    - images
    - audio
    - video
    """

    if not query:
        return []

    try:
        candidate_results = search_documents(
            query=query,
            limit=CANDIDATE_LIMIT,
        )
    except Exception:
        return []

    if not candidate_results:
        return []

    ranked_results = []

    for result in candidate_results:

        content = result.get("content", "")
        metadata = result.get("metadata", {})
        distance = result.get("distance")

        if not content:
            continue

        if distance is None:
            continue

        keyword_score = _keyword_match_score(
            query,
            content,
        )

        if not _is_relevant_candidate(
            distance,
            keyword_score,
        ):
            continue

        retrieval_score = _calculate_retrieval_score(
            distance,
            keyword_score,
        )

        ranked_results.append(
            {
                "content": content,
                "metadata": metadata,
                "distance": distance,
                "keyword_score": keyword_score,
                "retrieval_score": retrieval_score,
                "context_expanded": False,
            }
        )

    if not ranked_results:
        return []

    ranked_results.sort(
        key=lambda item: item["retrieval_score"],
        reverse=True,
    )

    # Expand related chunks from the same document.
    expanded_results = _expand_document_context(
        ranked_results
    )

    # Preserve document/chunk order after expansion.
    # This is important for OCR'd tables and multi-page documents.
    final_results = []

    seen_chunks = set()

    for item in expanded_results:

        metadata = item.get("metadata") or {}

        key = (
            metadata.get("document_id"),
            metadata.get("chunk_index"),
        )

        if key in seen_chunks:
            continue

        seen_chunks.add(key)
        final_results.append(item)

    final_limit = (
        limit
        if isinstance(limit, int) and limit > 0
        else FINAL_RESULT_LIMIT
    )

    return final_results[:final_limit]