import asyncio
import os
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1
        )
        page = await context.new_page()

        print("[1] Navigating to http://127.0.0.1:8088 ...")
        await page.goto("http://127.0.0.1:8088", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        # Close setup wizard if open
        await page.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.style.display = 'none';
            const b = document.getElementById('wizardBackdrop');
            if (b) b.style.display = 'none';
        }""")
        await page.wait_for_timeout(500)

        # Check SSID display
        ssid_text = await page.inner_text("#wifiSsidVal")
        print(f"[2] Initial SSID text: '{ssid_text}'")
        assert ssid_text == "••••••••", f"Expected '••••••••' but got '{ssid_text}'"

        # Check toggle button
        btn_toggle = await page.query_selector("#btnToggleSsid")
        assert btn_toggle is not None, "#btnToggleSsid not found"

        # Test clicking toggle to reveal
        await page.evaluate("() => toggleSsidVisibility()")
        await page.wait_for_timeout(300)
        revealed_ssid = await page.inner_text("#wifiSsidVal")
        print(f"[3] Revealed SSID (length: {len(revealed_ssid)}): '{revealed_ssid[:3]}***'")
        assert revealed_ssid != "••••••••", "SSID should be revealed after toggle"

        # Test clicking toggle to hide again
        await page.evaluate("() => toggleSsidVisibility()")
        await page.wait_for_timeout(300)
        rehidden_ssid = await page.inner_text("#wifiSsidVal")
        print(f"[4] Re-hidden SSID: '{rehidden_ssid}'")
        assert rehidden_ssid == "••••••••", "SSID should be hidden again"

        # Check Zoom Popup
        await page.evaluate("() => toggleZoomPopup('camLeft')")
        await page.wait_for_timeout(500)

        # Verify 0 25 50 75 100 buttons are REMOVED
        preset_count = await page.evaluate("() => document.querySelectorAll('#zoomPopup_camLeft .zoom-preset-btn').length")
        print(f"[5] Zoom preset buttons count: {preset_count}")
        assert preset_count == 0, f"Expected 0 preset buttons, found {preset_count}"

        # Check popup bounding box & zero overflow
        box = await page.evaluate("""() => {
            const popup = document.getElementById('zoomPopup_camLeft');
            const rect = popup.getBoundingClientRect();
            return {
                left: rect.left,
                right: rect.right,
                width: rect.width,
                windowWidth: window.innerWidth,
                overflowRight: rect.right > window.innerWidth,
                overflowLeft: rect.left < 0
            };
        }""")
        print(f"[6] Zoom popup bounding box: {box}")
        assert not box["overflowRight"], f"Popup overflows right: {box}"
        assert not box["overflowLeft"], f"Popup overflows left: {box}"

        # Adjust zoom slider to 45%
        await page.evaluate("() => setZoomPercent('camLeft', 45)")
        await page.wait_for_timeout(500)

        # Ensure SSID is masked as ••••••••
        final_ssid = await page.inner_text("#wifiSsidVal")
        print(f"[7] Final SSID before screenshot: '{final_ssid}'")
        assert final_ssid == "••••••••", "SSID must be masked before screenshot!"

        # Ensure wizard modal is not blocking
        await page.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.style.display = 'none';
        }""")

        screenshot_path = "/root/cctv_dashboard/docs/screenshots/desktop_preview.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        await page.screenshot(path=screenshot_path)
        print(f"[8] Successfully captured clean screenshot to: {screenshot_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
