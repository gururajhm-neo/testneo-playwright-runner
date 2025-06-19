import asyncio
from playwright.async_api import async_playwright

async def test_form_submission():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # headless for CI/CD
        page = await browser.new_page()

        await page.goto("https://httpbin.org/forms/post")
        
        # Fill actual existing form fields
        await page.fill('input[name="custname"]', "Test User")
        await page.fill('input[name="custtel"]', "123-456-7890")
        await page.fill('input[name="custemail"]', "test@example.com")
        
        # Submit the form
        await page.click('button')  # Only button is the submit button
        
        # Wait and check for response
        await page.wait_for_selector('pre', timeout=10000)
        content = await page.inner_text('pre')

        assert "Test User" in content, "Form submission failed"
        print("Form submission test completed successfully!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_form_submission())

