import json


def build_rag_context(knowledge):
    """
    Convert retrieved RAG knowledge into clean context
    that can be provided to the LLM.

    The knowledge has already been retrieved and filtered
    by the RAG retriever.

    Retrieved knowledge may come from:
        - Documents
        - PDFs
        - Scanned PDFs
        - Images
        - Audio
        - Video
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

        media_type = metadata.get(
            "media_type",
            "",
        )

        processing_method = metadata.get(
            "processing_method",
            "",
        )

        source_info = (
            f"Source: {source}"
        )

        if media_type:
            source_info += (
                f"\nMedia type: {media_type}"
            )

        if processing_method:
            source_info += (
                f"\nProcessing method: "
                f"{processing_method}"
            )

        formatted_knowledge.append(
            f"{index}. {source_info}\n"
            f"{content}"
        )

    if not formatted_knowledge:
        return ""

    knowledge_text = "\n\n".join(
        formatted_knowledge
    )

    return (
        "\n\n"
        "UPLOADED FILE KNOWLEDGE:\n\n"

        "The following information was extracted from "
        "files uploaded by the user and is available to "
        "you as context. The files may be documents, "
        "PDFs, images, audio, or video.\n\n"

        f"{knowledge_text}\n\n"

        "GROUNDING INSTRUCTIONS:\n"
        "Use the uploaded file knowledge above as the "
        "primary source when the user's question relates "
        "to those files.\n"

        "If the answer is present in the uploaded file "
        "knowledge, answer the user directly using that "
        "information.\n"

        "Do not say that you cannot access the user's "
        "file, image, audio, video, device data, or "
        "personal information when the requested "
        "information is explicitly present in the "
        "uploaded file knowledge.\n"

        "For example, if an uploaded screenshot contains "
        "screen-time information, use the screen-time "
        "values extracted from that screenshot to answer "
        "the user's question. Do not tell the user to "
        "check their phone settings.\n"

        "If an uploaded resume contains a CGPA or project "
        "names, use those values directly when answering "
        "questions about that resume.\n"

        "If an uploaded audio or video transcript contains "
        "information requested by the user, use that "
        "transcribed information directly.\n"

        "Do not invent information that is not present in "
        "the uploaded file knowledge.\n"

        "If the uploaded file knowledge genuinely does "
        "not contain the requested information, clearly "
        "state that the available file information is "
        "insufficient."
    )


def build_execution_context(execution):
    """
    Convert executor results into clean context
    that can be given to the LLM.

    Supports both:
        1. Existing single-step execution
        2. New multi-step execution
    """

    if not execution:
        return ""

    # ==============================================
    # MULTI-STEP EXECUTION
    # ==============================================

    steps = execution.get("steps")

    if isinstance(steps, list):

        contexts = []

        for index, step in enumerate(
            steps,
            start=1,
        ):

            if not isinstance(step, dict):
                continue

            step_context = build_execution_context(
                step
            )

            if step_context:
                contexts.append(
                    f"\nStep {index} result:"
                    f"{step_context}"
                )

        if not contexts:
            return ""

        return (
            "\n\n"
            "Multi-step tool execution results:\n"
            + "\n".join(contexts)
            + "\n\n"
            "Use the results from the completed steps "
            "when answering the user's request. "
            "Do not invent results that are not present."
        )

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
    # JOB SEARCH
    # ==============================================

    if action == "search_jobs":

        jobs = execution.get(
            "jobs",
            [],
        )

        search_status = execution.get(
            "search_status",
            "",
        )

        if not jobs:

            if search_status == "verification_timeout":
                return (
                    "\n\n"
                    "Job verification result:\n"
                    "The search found candidate URLs, but verification "
                    "timed out before any verified job could be returned.\n\n"
                    "Do not present unverified candidates as verified jobs. "
                    "Do not invent job listings."
                )

            return (
                "\n\n"
                "Verified job search result:\n"
                "No verified jobs were found for this request.\n\n"
                "Do not invent or fabricate job listings."
            )

        formatted_jobs = []

        for index, job in enumerate(
            jobs,
            start=1,
        ):

            if not isinstance(job, dict):
                continue

            # Keep the LLM context focused. The verifier retains the raw
            # page content, which can be very large. Include the useful
            # structured fields plus a bounded content excerpt.
            job_for_context = {
                "title": job.get("title", ""),
                "job_url": job.get("url", ""),
                "application_url": (
                    job.get("application_url")
                    or job.get("url", "")
                ),
                "job_status": job.get("job_status", "unknown"),
                "source_title": job.get("source_title", ""),
                "verified": job.get("status") == "verified",
                "job_metadata": job.get("job_metadata", {}),
                "content_excerpt": str(
                    job.get("content", "")
                )[:5000],
            }

            metadata = job_for_context.get("job_metadata")

            if isinstance(metadata, dict):
                description = metadata.get("description")
                if isinstance(description, str):
                    metadata = dict(metadata)
                    metadata["description"] = description[:3000]
                    job_for_context["job_metadata"] = metadata

            job_text = json.dumps(
                job_for_context,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

            formatted_jobs.append(
                f"JOB {index}:\n"
                f"{job_text}"
            )

        jobs_text = "\n\n".join(
            formatted_jobs
        )

        return (
            "\n\n"
            "VERIFIED JOB SEARCH RESULTS:\n\n"
            f"{jobs_text}\n\n"

            "IMPORTANT JOB SEARCH GROUNDING RULES:\n"
            "These job listings were returned by the "
            "job-search tool.\n"

            "Treat these results as the source of truth.\n"

            "Only describe jobs that are present in the "
            "results above.\n"

            "Do not invent or fabricate company names, "
            "job titles, salaries, locations, skills, "
            "requirements, application URLs, or job listings.\n"
            "Treat only records marked verified=true as verified jobs.\n"

            "Do not replace missing information with "
            "examples or assumptions.\n"

            "If a field is missing from a job result, "
            "say that the information was not available.\n"

            "If no verified jobs were returned, clearly "
            "tell the user that no verified jobs were found."
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