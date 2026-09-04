import asyncio
import pprint

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job


JOB_URL = "https://wellfound.com/jobs/4607376-software-engineer-ii-backend"


async def main():

    print("Fetching job page...")

    job = await fetch_job_page(JOB_URL)

    print("\nAnalyzing job description...")

    result = await analyze_job(job)

    print("\nRESULT:")
    pprint.pp(result)


asyncio.run(main())
