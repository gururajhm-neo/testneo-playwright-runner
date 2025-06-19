import asyncio
from playwright.async_api import async_playwright

async def test_google_search():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://google.com")
        await page.fill('input[name="q"]', "Playwright testing")
        await page.press('input[name="q"]', "Enter")
        
        await page.wait_for_selector('h3')
        results = await page.query_selector_all('h3')
        
        print(f"Found {len(results)} search results")
        assert len(results) > 0, "No search results found"
        
        await browser.close()
        print("Google search test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_google_search())