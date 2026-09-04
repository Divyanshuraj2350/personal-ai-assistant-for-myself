from app.rag.store import search_documents


RELEVANCE_THRESHOLD = 1.25


def retrieve_relevant_knowledge(
    query,
    limit=3,
):
    """
    Retrieve relevant knowledge from the RAG store
    for the user's current query.

    Only sufficiently relevant results are returned.
    """

    if not query:
        return []

    results = search_documents(
        query=query,
        limit=limit,
    )

    if not results:
        return []

    knowledge = []

    for result in results:

        content = result.get(
            "content",
            "",
        )

        metadata = result.get(
            "metadata",
            {},
        )

        distance = result.get(
            "distance",
        )

        if not content:
            continue

        if distance is None:
            continue

        if distance > RELEVANCE_THRESHOLD:
            continue

        knowledge.append(
            {
                "content": content,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return knowledge