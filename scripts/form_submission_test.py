import asyncio
from playwright.async_api import async_playwright

async def test_form_submission():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://httpbin.org/forms/post")
        
        # Fill form fields
        await page.fill('input[name="custname"]', "Test User")
        await page.fill('input[name="custtel"]', "123-456-7890")
        await page.fill('input[name="custemail"]', "test@example.com")
        await page.select_option('select[name="size"]', 'large')
        await page.check('input[name="topping"][value="bacon"]')
        
        # Submit form
        await page.click('input[type="submit"]')
        
        # Verify submission
        await page.wait_for_selector('pre')
        content = await page.inner_text('pre')
        
        assert "Test User" in content, "Form submission failed"
        print("Form submission test completed successfully!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_form_submission())