import asyncio
import os
import pprint

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_matcher import match_job
from app.agent.resume_ai import create_ai_resume
from app.agent.resume_validator import validate_resume
from app.agent.resume_renderer import render_resume_pdf


JOB_URL = (
    "https://wellfound.com/jobs/"
    "4607376-software-engineer-ii-backend"
)


async def main():

    print("Fetching job...")

    job_page = await fetch_job_page(
        JOB_URL
    )

    print("Analyzing job...")

    analysis = await analyze_job(
        job_page
    )

    if analysis["status"] != "success":

        pprint.pp(analysis)
        return

    job = analysis["job"]

    print("Matching job...")

    match_result = match_job(
        job
    )

    print("Generating resume...")

    ai_result = await create_ai_resume(
        job,
        match_result,
    )

    if ai_result["status"] != "success":

        pprint.pp(ai_result)
        return

    resume = ai_result["resume"]

    print("Validating resume...")

    validation = validate_resume(
        resume
    )

    print("\nVALIDATION RESULT:")

    pprint.pp(validation)

    if not validation.get("valid"):

        print(
            "\nResume is invalid."
            "\nPDF will NOT be generated."
        )

        return

    print(
        "\nResume is valid."
    )

    print(
        "Rendering PDF..."
    )

    result = render_resume_pdf(
        resume
    )

    print(
        "\nPDF RESULT:"
    )

    pprint.pp(result)

    if result.get("status") == "success":

        path = result["path"]

        print(
            "\nPDF created successfully."
        )

        print(
            f"Path: {path}"
        )

        print(
            f"Exists: {os.path.exists(path)}"
        )

        if os.path.exists(path):

            print(
                f"Size: "
                f"{os.path.getsize(path)} bytes"
            )


asyncio.run(main())