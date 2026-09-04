from app.agent.tools import get_tool

from app.agent.web_tool import web_search
from app.agent.calculator import calculate
from app.agent.web_cleaner import clean_results
from app.agent.relevance import filter_relevant_results

from app.agent.email_tool import generate_email_draft
from app.agent.approval import create_approval_request

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job


async def execute_plan(
    plan,
    message,
):
    """
    Execute the action selected by the planner.

    The executor should return structured data.
    It should not decide how the final LLM response
    is written. That responsibility belongs to the
    context builder and the main AI pipeline.
    """

    action = plan.get("action")

    tool = get_tool(
        action
    )

    # ==================================================
    # INVALID / UNKNOWN ACTION
    # ==================================================

    if not action or tool is None:

        return {
            "status": "error",
            "tool": tool,
            "action": action,
            "message": message,
            "error": "Unknown action requested.",
        }

    # ==================================================
    # CALCULATION
    # ==================================================

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

    # ==================================================
    # EMAIL
    # ==================================================

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

    # ==================================================
    # JOB ANALYSIS
    # ==================================================

    if action == "analyze_job":

        import re

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

        url = url_match.group(0).rstrip(
            ".,);]"
        )

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

        if job_page.get("status") != "success":

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

        try:

            analysis = await analyze_job(
                job_page
            )

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

        if analysis.get("status") != "success":

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

    # ==================================================
    # WEB SEARCH
    # ==================================================

    if plan["action"] == "search_web":

        try:

            raw_results = await web_search(
                message
            )

            relevant_results = filter_relevant_results(
                query=message,
                results=raw_results,
                limit=3,
            )

            cleaned_results = clean_results(
                relevant_results
            )

            return {
                "status": "completed",
                "tool": tool,
                "action": plan["action"],
                "message": message,
                "results": cleaned_results,
            }

        except Exception as error:

            return {
                "status": "error",
                "tool": tool,
                "action": plan["action"],
                "message": message,
                "error": str(error),
            }

    # ==================================================
    # OTHER ACTIONS REQUIRING APPROVAL
    # ==================================================

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

    # ==================================================
    # NORMAL CHAT / NO TOOL EXECUTION
    # ==================================================

    return {
        "status": "ready",
        "tool": tool,
        "action": action,
        "message": message,
    }