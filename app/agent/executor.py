import asyncio
import re

from app.agent.tools import get_tool

from app.agent.web_tool import web_search
from app.agent.calculator import calculate
from app.agent.web_cleaner import clean_results
from app.agent.relevance import filter_relevant_results

from app.agent.email_tool import generate_email_draft
from app.agent.approval import create_approval_request

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_search import search_jobs
from app.agent.job_verifier import discover_verified_jobs


# ==========================================================
# CONFIGURATION
# ==========================================================

MAX_JOBS_TO_ANALYZE = 5

# Maximum time allowed for one Qwen analysis.
SINGLE_JOB_ANALYSIS_TIMEOUT = 130


# ==========================================================
# MAIN EXECUTOR
# ==========================================================

async def execute_plan(
    plan,
    message,
):
    """
    Execute an agent plan.

    Supports:

    1. Single-step plans

       {
           "action": "search_web"
       }

    2. Multi-step plans

       {
           "steps": [
               {"action": "search_jobs"},
               {"action": "analyze_jobs"}
           ]
       }

    The executor returns structured data.
    It does not decide how the final LLM response
    should be written.
    """

    # ======================================================
    # MULTI-STEP EXECUTION
    # ======================================================

    steps = plan.get("steps")

    if isinstance(steps, list):

        if not steps:

            return {
                "status": "error",
                "message": message,
                "error": (
                    "Multi-step plan contains no steps."
                ),
                "steps": [],
            }

        step_results = []

        for index, step in enumerate(
            steps,
            start=1,
        ):

            if not isinstance(
                step,
                dict,
            ):

                return {
                    "status": "error",
                    "message": message,
                    "error": (
                        f"Invalid plan step {index}."
                    ),
                    "steps": step_results,
                }

            step_action = step.get(
                "action"
            )

            if not step_action:

                return {
                    "status": "error",
                    "message": message,
                    "error": (
                        f"Step {index} has no action."
                    ),
                    "steps": step_results,
                }

            # ==================================================
            # STEP MESSAGE
            # ==================================================

            step_message = step.get(
                "message",
                message,
            )

            # ==================================================
            # PREVIOUS RESULT PLACEHOLDER
            # ==================================================

            if "{previous_result}" in step_message:

                if not step_results:

                    return {
                        "status": "error",
                        "message": message,
                        "error": (
                            f"Step {index} requested "
                            "previous_result, but no "
                            "previous step exists."
                        ),
                        "steps": step_results,
                    }

                previous_result = (
                    step_results[-1]["result"]
                )

                if isinstance(
                    previous_result,
                    dict,
                ):

                    previous_value = (
                        previous_result.get(
                            "result",
                            previous_result,
                        )
                    )

                else:

                    previous_value = (
                        previous_result
                    )

                step_message = step_message.replace(
                    "{previous_result}",
                    str(previous_value),
                )

            # ==================================================
            # PREVIOUS CONTEXT
            # ==================================================

            previous_context = ""

            if step_results:

                previous_context = (
                    "\n\nPrevious step results:\n"
                )

                for previous_step in step_results:

                    previous_context += (
                        f"Step {previous_step['step']}: "
                        f"{previous_step['result']}\n"
                    )

            # --------------------------------------------------
            # Calculation should not receive huge previous
            # context.
            # --------------------------------------------------

            if step_action == "calculate":

                execution_message = (
                    step_message
                )

            else:

                execution_message = (
                    step_message
                    + previous_context
                )

            # ==================================================
            # STEP PLAN
            # ==================================================

            step_plan = {
                "intent": step.get(
                    "intent",
                    plan.get("intent"),
                ),

                "action": step_action,

                "requires_approval": step.get(
                    "requires_approval",
                    False,
                ),
            }
            # ==================================================
            # PASS STRUCTURED JOB RESULTS TO ANALYZE_JOBS
            # ==================================================

            if (
                step_action == "analyze_jobs"
                and step_results
            ):

                previous_result = step_results[-1].get(
                    "result",
                    {},
                )

                if isinstance(
                    previous_result,
                    dict,
                ):

                    step_plan["_previous_jobs"] = (
                        previous_result.get(
                            "jobs",
                            [],
                        )
                    )

            # ==================================================
            # EXECUTE STEP
            # ==================================================

            result = await execute_plan(
                plan=step_plan,
                message=execution_message,
            )

            step_results.append(
                {
                    "step": index,
                    "action": step_action,
                    "message": step_message,
                    "result": result,
                }
            )

            # ==================================================
            # STOP ON ERROR
            # ==================================================

            if result.get(
                "status"
            ) == "error":

                return {
                    "status": "error",
                    "message": message,
                    "steps": step_results,
                    "error": (
                        f"Step {index} failed: "
                        f"{result.get('error', 'Unknown error')}"
                    ),
                }

            # ==================================================
            # STOP FOR APPROVAL
            # ==================================================

            if result.get("status") in {
                "pending_approval",
                "approval_required",
            }:

                return {
                    "status": result.get(
                        "status"
                    ),
                    "message": message,
                    "steps": step_results,
                    "approval_id": result.get(
                        "approval_id"
                    ),
                    "tool": result.get(
                        "tool"
                    ),
                    "action": result.get(
                        "action"
                    ),
                    "recipient": result.get(
                        "recipient"
                    ),
                    "subject": result.get(
                        "subject"
                    ),
                    "body": result.get(
                        "body"
                    ),
                    "approved": result.get(
                        "approved"
                    ),
                }

        # ======================================================
        # ALL STEPS COMPLETED
        # ======================================================

        return {
            "status": "completed",
            "message": message,
            "steps": step_results,
        }

    # ======================================================
    # SINGLE-STEP EXECUTION
    # ======================================================

    action = plan.get(
        "action"
    )

    # ------------------------------------------------------
    # analyze_jobs is an internal compound action.
    # It does not need to be registered in get_tool().
    # ------------------------------------------------------

    if action == "analyze_jobs":

        tool = "job_analyzer"

    else:

        tool = get_tool(
            action
        )

    # ======================================================
    # INVALID ACTION
    # ======================================================

    if not action or tool is None:

        return {
            "status": "error",
            "tool": tool,
            "action": action,
            "message": message,
            "error": (
                "Unknown action requested."
            ),
        }

    # ======================================================
    # CALCULATION
    # ======================================================

    if action == "calculate":

        try:

            result = calculate(
                message
            )

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not calculate the expression: "
                    f"{error}"
                ),
            }

        if result is None:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not calculate the expression."
                ),
            }

        return {
            "status": "completed",
            "tool": tool,
            "action": action,
            "message": message,
            "result": result,
        }

    # ======================================================
    # EMAIL
    # ======================================================

    if action == "draft_email":

        try:

            draft = await generate_email_draft(
                message
            )

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not generate the email draft: "
                    f"{error}"
                ),
            }

        if draft.get("status") == "error":

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": draft.get(
                    "error",
                    "Could not generate the email draft.",
                ),
            }

        try:

            approval_request = (
                create_approval_request(
                    draft
                )
            )

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not create the approval request: "
                    f"{error}"
                ),
            }

        return {
            "status": "pending_approval",
            "tool": tool,
            "action": action,
            "message": message,
            "approval_id":
                approval_request["approval_id"],
            "recipient":
                approval_request["recipient"],
            "subject":
                approval_request["subject"],
            "body":
                approval_request["body"],
            "approved":
                approval_request["approved"],
        }

    # ======================================================
    # ANALYZE ONE JOB URL
    # ======================================================

    if action == "analyze_job":

        url_match = re.search(
            r"https?://[^\s]+",
            message,
            re.IGNORECASE,
        )

        if not url_match:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "No job URL found in the request."
                ),
            }

        url = url_match.group(
            0
        ).rstrip(
            ".,);]"
        )

        # --------------------------------------------------
        # FETCH
        # --------------------------------------------------

        try:

            job_page = await fetch_job_page(
                url
            )

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not fetch the job page: "
                    f"{error}"
                ),
            }

        if job_page.get(
            "status"
        ) != "success":

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": job_page.get(
                    "error",
                    "Could not fetch the job page.",
                ),
            }

        # --------------------------------------------------
        # ANALYZE
        # --------------------------------------------------

        try:

            analysis = await asyncio.wait_for(
                analyze_job(
                    job_page
                ),
                timeout=SINGLE_JOB_ANALYSIS_TIMEOUT,
            )

        except asyncio.TimeoutError:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Job analysis timed out after "
                    f"{SINGLE_JOB_ANALYSIS_TIMEOUT} seconds."
                ),
            }

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not analyze the job: "
                    f"{error}"
                ),
            }

        if analysis.get(
            "status"
        ) != "success":

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": analysis.get(
                    "error",
                    "Could not analyze the job.",
                ),
            }

        return {
            "status": "completed",
            "tool": tool,
            "action": action,
            "message": message,
            "job": analysis["job"],
            "source_url":
                analysis["source_url"],
        }

    # ======================================================
    # SEARCH JOBS
    # ======================================================

    if action == "search_jobs":

        try:

            search_result = await search_jobs(
                message
            )

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Could not search for jobs: "
                    f"{error}"
                ),
            }

        if not isinstance(
            search_result,
            dict,
        ):

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "Job search returned an invalid result."
                ),
            }

        if search_result.get(
            "status"
        ) == "error":

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": search_result.get(
                    "error",
                    "Could not search for jobs.",
                ),
            }

        raw_jobs = search_result.get(
            "jobs",
            [],
        )

        if not isinstance(
            raw_jobs,
            list,
        ):

            raw_jobs = []

        print(
            "\n========== JOB SEARCH DEBUG =========="
        )

        print(
            "RAW JOB COUNT:",
            len(raw_jobs),
        )

        print(
            "Starting job verification..."
        )

        # ==================================================
        # VERIFY
        # ==================================================

        try:

            verified_jobs = await asyncio.wait_for(
                discover_verified_jobs(
                    raw_jobs,
                    limit=5,
                ),
                timeout=45,
            )

        except asyncio.TimeoutError:

            print(
                "[JOB SEARCH] "
                "Verification exceeded 45 seconds."
            )

            verified_jobs = []

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            print(
                "[JOB SEARCH] "
                f"Verification error: {exc}"
            )

            verified_jobs = []

        # ==================================================
        # RETURN VERIFIED JOBS
        # ==================================================

        print(
            "\nJOB VERIFICATION FINISHED"
        )

        print(
            "VERIFIED JOB COUNT:",
            len(verified_jobs),
        )

        return {
            "status": "completed",
            "tool": tool,
            "action": action,
            "message": message,
            "jobs": verified_jobs,
            "raw_job_count": len(raw_jobs),
            "verified_job_count": len(verified_jobs),
            "search_status": search_result.get(
                "status",
                "completed",
            ),
        }

    # ======================================================
    # ANALYZE MULTIPLE JOBS
    # ======================================================

    if action == "analyze_jobs":

        print(
            "\n========== JOB ANALYSIS DEBUG =========="
        )

        # --------------------------------------------------
        # The previous search result should contain jobs.
        # --------------------------------------------------

        jobs = []

        # First try to recover jobs from the plan message.
        #
        # In the compound executor, previous_context is
        # included in the message. We therefore need to
        # inspect the actual recursive execution context.
        #
        # The preferred path is handled below by extracting
        # the structured previous result marker.
        # --------------------------------------------------

        previous_jobs = plan.get(
            "_previous_jobs"
        )

        if isinstance(
            previous_jobs,
            list,
        ):

            jobs = previous_jobs

        # --------------------------------------------------
        # Fallback:
        # If no structured jobs were passed, return a clear
        # error instead of sending text blobs to Qwen.
        # --------------------------------------------------

        if not jobs:

            print(
                "NO STRUCTURED JOBS RECEIVED"
            )

            print(
                "========================================\n"
            )

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "analyze_jobs requires the verified "
                    "job results from search_jobs."
                ),
                "jobs": [],
            }

        # --------------------------------------------------
        # Limit number of jobs.
        # --------------------------------------------------

        jobs = jobs[
            :MAX_JOBS_TO_ANALYZE
        ]

        print(
            "JOBS RECEIVED FOR ANALYSIS:",
            len(jobs),
        )

        analyzed_jobs = []
        failed_jobs = []

        # ==================================================
        # ANALYZE SEQUENTIALLY
        # ==================================================

        for index, job in enumerate(
            jobs,
            start=1,
        ):

            if not isinstance(
                job,
                dict,
            ):

                failed_jobs.append(
                    {
                        "index": index,
                        "error": (
                            "Invalid job object."
                        ),
                    }
                )

                continue

            url = job.get(
                "url",
                "",
            )

            title = job.get(
                "title",
                "",
            )

            content = job.get(
                "content",
                "",
            )

            print(
                f"Analyzing job {index}: {title}"
            )

            # --------------------------------------------------
            # Some verifier implementations return content
            # directly. Others may only return URL/title.
            #
            # If content is missing, fetch the page again.
            # --------------------------------------------------

            if not content and url:

                try:

                    fetched = await asyncio.wait_for(
                        fetch_job_page(
                            url
                        ),
                        timeout=30,
                    )

                except asyncio.TimeoutError:

                    failed_jobs.append(
                        {
                            "index": index,
                            "title": title,
                            "url": url,
                            "error": (
                                "Job page fetch timed out."
                            ),
                        }
                    )

                    continue

                except Exception as error:

                    failed_jobs.append(
                        {
                            "index": index,
                            "title": title,
                            "url": url,
                            "error": (
                                f"Job page fetch failed: {error}"
                            ),
                        }
                    )

                    continue

                if fetched.get(
                    "status"
                ) != "success":

                    failed_jobs.append(
                        {
                            "index": index,
                            "title": title,
                            "url": url,
                            "error": fetched.get(
                                "error",
                                "Could not fetch job page.",
                            ),
                        }
                    )

                    continue

                job_data = fetched

            else:

                # Build the exact structure expected by
                # analyze_job().
                job_data = {
                    "status": "success",
                    "url": url,
                    "title": title,
                    "content": content,
                }

            # --------------------------------------------------
            # ANALYZE WITH TIMEOUT
            # --------------------------------------------------

            try:

                analysis = await asyncio.wait_for(
                    analyze_job(
                        job_data
                    ),
                    timeout=SINGLE_JOB_ANALYSIS_TIMEOUT,
                )

            except asyncio.TimeoutError:

                failed_jobs.append(
                    {
                        "index": index,
                        "title": title,
                        "url": url,
                        "error": (
                            "Qwen analysis timed out "
                            f"after {SINGLE_JOB_ANALYSIS_TIMEOUT} seconds."
                        ),
                    }
                )

                print(
                    f"Analysis timeout: job {index}"
                )

                continue

            except Exception as error:

                failed_jobs.append(
                    {
                        "index": index,
                        "title": title,
                        "url": url,
                        "error": str(error),
                    }
                )

                print(
                    f"Analysis failed: {error}"
                )

                continue

            # --------------------------------------------------
            # SUCCESS
            # --------------------------------------------------

            if analysis.get(
                "status"
            ) == "success":

                analyzed_job = (
                    analysis.get(
                        "job",
                        {},
                    )
                )

                # Preserve original search metadata.
                if isinstance(
                    analyzed_job,
                    dict,
                ):

                    analyzed_job[
                        "source_url"
                    ] = analysis.get(
                        "source_url",
                        url,
                    )

                    analyzed_job[
                        "search_title"
                    ] = title

                    analyzed_job[
                        "search_score"
                    ] = job.get(
                        "search_score"
                    )

                    analyzed_job[
                        "verified"
                    ] = job.get(
                        "verified",
                        True,
                    )

                analyzed_jobs.append(
                    analyzed_job
                )

                print(
                    f"Analysis successful: job {index}"
                )

            else:

                failed_jobs.append(
                    {
                        "index": index,
                        "title": title,
                        "url": url,
                        "error": analysis.get(
                            "error",
                            "Unknown analysis error.",
                        ),
                    }
                )

                print(
                    f"Analysis rejected: job {index}"
                )

        # ==================================================
        # SUMMARY
        # ==================================================

        print(
            "\nJOB ANALYSIS FINISHED"
        )

        print(
            "SUCCESSFUL:",
            len(analyzed_jobs),
        )

        print(
            "FAILED:",
            len(failed_jobs),
        )

        print(
            "========================================\n"
        )

        # --------------------------------------------------
        # If all jobs failed, return error.
        # --------------------------------------------------

        if not analyzed_jobs:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": (
                    "None of the verified jobs could "
                    "be analyzed."
                ),
                "jobs": [],
                "failed_jobs": failed_jobs,
            }

        # --------------------------------------------------
        # Partial success is still success.
        # --------------------------------------------------

        return {
            "status": "completed",
            "tool": tool,
            "action": action,
            "message": message,
            "jobs": analyzed_jobs,
            "job_count": len(
                analyzed_jobs
            ),
            "failed_count": len(
                failed_jobs
            ),
            "failed_jobs": failed_jobs,
        }

    # ======================================================
    # WEB SEARCH
    # ======================================================

    if action == "search_web":

        try:

            raw_results = await web_search(
                message
            )

            relevant_results = (
                filter_relevant_results(
                    query=message,
                    results=raw_results,
                    limit=3,
                )
            )

            cleaned_results = clean_results(
                relevant_results
            )

            return {
                "status": "completed",
                "tool": tool,
                "action": action,
                "message": message,
                "results": cleaned_results,
            }

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": action,
                "message": message,
                "error": str(error),
            }

    # ======================================================
    # OTHER APPROVAL ACTIONS
    # ======================================================

    if plan.get(
        "requires_approval",
        False,
    ):

        return {
            "status": "approval_required",
            "tool": tool,
            "action": action,
            "message": message,
            "requires_approval": True,
        }

    # ======================================================
    # NORMAL CHAT
    # ======================================================

    return {
        "status": "ready",
        "tool": tool,
        "action": action,
        "message": message,
    }