import asyncio

from playwright.async_api import async_playwright


URL = "https://wellfound.com/jobs?job_listing_slug=4574566-forward-deployed-engineer-intern"


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        await page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        links = await page.locator("a").all()

        print(f"Found {len(links)} links\n")

        for link in links:

            text = (await link.inner_text()).strip()
            href = await link.get_attribute("href")

            if (
                "forward" in text.lower()
                or "engineer" in text.lower()
                or "4574566" in str(href).lower()
            ):
                print("TEXT:", repr(text))
                print("HREF:", href)
                print("-" * 60)

        await browser.close()


asyncio.run(main())
