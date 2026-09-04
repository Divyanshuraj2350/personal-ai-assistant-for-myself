import asyncio
import pprint

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_matcher import match_job


JOB_URL = "https://wellfound.com/jobs/4607376-software-engineer-ii-backend"


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

    print("Matching job with career profile...")

    result = match_job(
        analysis["job"]
    )

    print("\nMATCH RESULT:")
    pprint.pp(result)


asyncio.run(main())
