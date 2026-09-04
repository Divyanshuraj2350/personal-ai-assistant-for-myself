import json


def build_rag_context(knowledge):
    """
    Convert retrieved RAG knowledge into clean context
    that can be provided to the LLM.

    The knowledge has already been retrieved and filtered
    by the RAG retriever.
    """

    if not knowledge:
        return ""

    formatted_knowledge = []

    for index, item in enumerate(
        knowledge,
        start=1,
    ):

        content = item.get(
            "content",
            "",
        )

        metadata = item.get(
            "metadata",
            {},
        )

        if not content:
            continue

        source = metadata.get(
            "file_name",
            metadata.get(
                "source",
                "knowledge base",
            ),
        )

        formatted_knowledge.append(
            f"{index}. Source: {source}\n"
            f"{content}"
        )

    if not formatted_knowledge:
        return ""

    knowledge_text = "\n\n".join(
        formatted_knowledge
    )

    return (
        "\n\n"
        "Relevant knowledge retrieved from the knowledge base:\n\n"
        f"{knowledge_text}\n\n"
        "Use this information when it is relevant to the "
        "user's request. Do not claim information that is "
        "not supported by the retrieved knowledge."
    )


def build_execution_context(execution):
    """
    Convert an executor result into clean context
    that can be given to the LLM.

    The LLM should use this context when answering
    the user's original request.
    """

    if not execution:
        return ""

    status = execution.get("status")
    action = execution.get("action")

    # ==============================================
    # NORMAL CHAT / NO TOOL RESULT
    # ==============================================

    if status == "ready":
        return ""

    # ==============================================
    # ERROR
    # ==============================================

    if status == "error":

        error = execution.get(
            "error",
            "The requested tool could not complete.",
        )

        return (
            "\n\n"
            "Tool execution result:\n"
            f"The tool could not complete the request: {error}\n\n"
            "Be honest about this limitation. "
            "Do not invent a successful tool result."
        )

    # ==============================================
    # PENDING APPROVAL
    # ==============================================

    if status in {
        "pending_approval",
        "approval_required",
    }:

        return ""

    # ==============================================
    # CALCULATION
    # ==============================================

    if action == "calculate":

        result = execution.get("result")

        if result is None:
            return ""

        return (
            "\n\n"
            "Calculator result:\n"
            f"{result}\n\n"
            "Use this result directly when answering. "
            "Do not recalculate a different value."
        )

    # ==============================================
    # WEB SEARCH
    # ==============================================

    if action == "search_web":

        results = execution.get(
            "results",
            [],
        )

        if not results:

            return (
                "\n\n"
                "Web search result:\n"
                "No useful results were found.\n\n"
                "Do not claim that you searched the web "
                "successfully if no useful result is available."
            )

        formatted_results = []

        for index, result in enumerate(
            results,
            start=1,
        ):

            title = result.get(
                "title",
                "",
            )

            url = result.get(
                "url",
                "",
            )

            content = result.get(
                "content",
                "",
            )

            formatted_results.append(
                f"{index}. {title}\n"
                f"Source: {url}\n"
                f"Content: {content}"
            )

        results_text = "\n\n".join(
            formatted_results
        )

        return (
            "\n\n"
            "Current web search results:\n\n"
            f"{results_text}\n\n"
            "Answer the user's question using these web results. "
            "Do not say that you do not have internet access. "
            "If the results are incomplete, say what is uncertain."
        )

    # ==============================================
    # JOB ANALYSIS
    # ==============================================

    if action == "analyze_job":

        job = execution.get(
            "job",
            {},
        )

        source_url = execution.get(
            "source_url",
            "",
        )

        if not job:
            return ""

        job_text = json.dumps(
            job,
            indent=2,
            ensure_ascii=False,
        )

        return (
            "\n\n"
            "Job analysis result:\n\n"
            f"Source: {source_url}\n\n"
            f"{job_text}\n\n"
            "Use this job analysis when answering "
            "questions about the job."
        )

    # ==============================================
    # GENERIC COMPLETED TOOL
    # ==============================================

    if status == "completed":

        safe_execution = {
            key: value
            for key, value in execution.items()
            if key not in {
                "message",
            }
        }

        execution_text = json.dumps(
            safe_execution,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        return (
            "\n\n"
            "Tool execution result:\n\n"
            f"{execution_text}\n\n"
            "Use this information when relevant "
            "to answer the user."
        )

    return ""