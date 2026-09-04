import pprint

from app.agent.career_profile import load_profile
from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_matcher import match_job
from app.agent.resume_builder import build_grounded_resume


import asyncio


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

    print("Building grounded resume...")

    profile = load_profile()

    resume = build_grounded_resume(
        profile,
        job,
        match_result,
    )

    print("\nGROUNDED RESUME:")

    pprint.pp(
        resume
    )


asyncio.run(main())