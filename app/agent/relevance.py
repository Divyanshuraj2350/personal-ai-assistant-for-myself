import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

embedding_model = SentenceTransformer(MODEL_NAME)


def calculate_relevance(query, result):

    title = result.get("title", "")
    content = result.get("content", "")

    result_text = f"{title}\n{content}"

    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True,
    )

    result_embedding = embedding_model.encode(
        result_text,
        normalize_embeddings=True,
    )

    score = float(
        np.dot(query_embedding, result_embedding)
    )

    return round(score, 3)


def filter_relevant_results(
    query,
    results,
    limit=3,
    threshold=0.35,
):

    scored_results = []

    for result in results:

        score = calculate_relevance(
            query,
            result,
        )

        result_copy = result.copy()
        result_copy["relevance_score"] = score

        scored_results.append(result_copy)

    scored_results.sort(
        key=lambda result: result["relevance_score"],
        reverse=True,
    )

    relevant = [
        result
        for result in scored_results
        if result["relevance_score"] >= threshold
    ]

    if not relevant and scored_results:
        relevant = scored_results[:1]

    return relevant[:limit]
