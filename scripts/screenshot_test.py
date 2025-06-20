import asyncio
import os
from playwright.async_api import async_playwright

async def test_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://example.com")
        
        # Create screenshots directory if it doesn't exist
        os.makedirs("screenshots", exist_ok=True)
        
        # Take screenshot
        await page.screenshot(path="screenshots/example_page.png")
        
        print("Screenshot saved to screenshots/example_page.png")
        print("Screenshot test completed successfully!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_screenshot())