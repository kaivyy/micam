import asyncio
from playwright.async_api import async_playwright

async def verify_mobile():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()

        print("Navigating mobile to http://127.0.0.1:8088 ...")
        await page.goto("http://127.0.0.1:8088", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Open zoom popup on mobile
        await page.click("#btnZoomLeft")
        await page.wait_for_timeout(400)

        # Click 2-Pass FSR tab
        await page.click("#tabFsr_camLeft")
        await page.wait_for_timeout(300)

        # Click 25% zoom
        btn_25 = await page.query_selector("#zoomPopup_camLeft button:has-text('25%')")
        if btn_25:
            await btn_25.click()
            await page.wait_for_timeout(400)

        mobile_screenshot = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739/fsr_2pass_mobile_zoom.png"
        await page.screenshot(path=mobile_screenshot)
        print(f"Mobile screenshot saved to: {mobile_screenshot}")

        await browser.close()
        return True

if __name__ == "__main__":
    asyncio.run(verify_mobile())
