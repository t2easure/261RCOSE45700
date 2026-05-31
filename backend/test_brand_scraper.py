import asyncio
from crawlers.brand_scraper import run_brand_scraper
from crawlers.instagram_playwright import run_instagram_playwright

async def main():
    await run_brand_scraper()
    await run_instagram_playwright()

asyncio.run(main())
