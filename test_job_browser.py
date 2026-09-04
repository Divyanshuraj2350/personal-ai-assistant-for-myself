import asyncio

from playwright.async_api import async_playwright


JOB_URL = "https://wellfound.com/jobs?job_listing_slug=4574566-forward-deployed-engineer-intern"


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        await page.goto(
            JOB_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(5000)

        print("TITLE:")
        print(await page.title())

        print("\nURL:")
        print(page.url)

        print("\nPAGE TEXT:")
        text = await page.locator("body").inner_text()

        print(text[:20000])

        await browser.close()


asyncio.run(main())
