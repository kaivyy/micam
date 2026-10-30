import asyncio
import os
from playwright.async_api import async_playwright

async def verify_dashboard():
    console_errors = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(f"[pageerror] {err}"))

        print("Navigating to http://127.0.0.1:8088 ...")
        await page.goto("http://127.0.0.1:8088", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 1. Verify canvas elements exist
        canvas_left = await page.query_selector("#fsrCanvas_camLeft")
        canvas_right = await page.query_selector("#fsrCanvas_camRight")
        print(f"Canvas Left present: {canvas_left is not None}")
        print(f"Canvas Right present: {canvas_right is not None}")
        assert canvas_left is not None, "fsrCanvas_camLeft missing"
        assert canvas_right is not None, "fsrCanvas_camRight missing"

        # 2. Check engine tabs in Zoom popup
        tab_svg_left = await page.query_selector("#tabSvg_camLeft")
        tab_fsr_left = await page.query_selector("#tabFsr_camLeft")
        print(f"Tab SVG Left present: {tab_svg_left is not None}")
        print(f"Tab FSR Left present: {tab_fsr_left is not None}")

        # 3. Open Zoom Popup on Cam Left
        btn_zoom_left = await page.query_selector("#btnZoomLeft")
        if btn_zoom_left:
            await btn_zoom_left.click()
            await page.wait_for_timeout(500)
            popup_open = await page.evaluate("() => document.getElementById('zoomPopup_camLeft').classList.contains('is-open')")
            print(f"Zoom Popup Left is open: {popup_open}")

        # 4. Test switching engine tabs
        await page.click("#tabSvg_camLeft")
        await page.wait_for_timeout(300)
        mode_after_svg = await page.evaluate("() => clarityModes['camLeft']")
        print(f"Mode after clicking SVG: {mode_after_svg}")

        await page.click("#tabFsr_camLeft")
        await page.wait_for_timeout(300)
        mode_after_fsr = await page.evaluate("() => clarityModes['camLeft']")
        print(f"Mode after clicking FSR: {mode_after_fsr}")

        # 5. Test Zoom slider presets (e.g. 50%)
        btn_50_pct = await page.query_selector("#zoomPopup_camLeft button:has-text('50%')")
        if btn_50_pct:
            await btn_50_pct.click()
            await page.wait_for_timeout(500)
            zoom_val = await page.evaluate("() => zoomPanState['camLeft'].percent")
            print(f"Zoom percent after clicking 50%: {zoom_val}%")

        # 6. Capture screenshot evidence of dashboard with FSR popup open
        screenshot_path = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739/fsr_2pass_zoom_active.png"
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")

        # 7. Check console errors
        print("Console errors count:", len(console_errors))
        if console_errors:
            for ce in console_errors:
                print("  !", ce)

        await browser.close()
        return len(console_errors) == 0

if __name__ == "__main__":
    success = asyncio.run(verify_dashboard())
    print("Verification Success:", success)
