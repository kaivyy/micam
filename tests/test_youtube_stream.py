import asyncio
import os
import urllib.request
import json
from playwright.async_api import async_playwright

async def run():
    print("[1] Testing YouTube Streaming Backend API...")
    req = urllib.request.urlopen("http://127.0.0.1:8088/api/youtube/status")
    status = json.loads(req.read().decode())
    assert "active" in status
    assert "stream_key_set" in status
    assert "lens" in status
    assert "quality" in status
    print(f"    Initial Status: active={status['active']}, lens={status['lens']}, quality={status['quality']}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1
        )
        page = await context.new_page()

        print("[2] Navigating to http://127.0.0.1:8088 ...")
        await page.goto("http://127.0.0.1:8088", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        # Close wizard if open
        await page.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.style.display = 'none';
            const b = document.getElementById('wizardBackdrop');
            if (b) b.style.display = 'none';
        }""")
        await page.wait_for_timeout(300)

        # Blur video elements for home privacy
        await page.evaluate("""() => {
            document.querySelectorAll('video, canvas, .video-player-wrapper').forEach(el => {
                el.style.filter = 'blur(18px)';
            });
        }""")

        print("[3] Verifying YouTube Live button in header...")
        btn_yt = await page.query_selector("#btnOpenYouTubeModal")
        assert btn_yt is not None, "YouTube button in header not found"
        await btn_yt.click()
        await page.wait_for_timeout(600)

        # Verify modal is open
        modal_open = await page.evaluate("""() => {
            const m = document.getElementById('youtubeModal');
            return m && m.classList.contains('open');
        }""")
        assert modal_open, "YouTube modal did not open after clicking button"
        print("    YouTube modal opened successfully.")

        # Test Guide accordion toggle
        print("[4] Testing Guide Accordion ('Cara Mengisi')...")
        guide_body_visible_init = await page.evaluate("""() => {
            const body = document.getElementById('ytGuideBody');
            return body && window.getComputedStyle(body).display !== 'none';
        }""")
        assert not guide_body_visible_init, "Guide body should initially be collapsed"

        btn_guide = await page.query_selector("#btnToggleYtGuide")
        assert btn_guide is not None, "Guide toggle button not found"
        await btn_guide.click()
        await page.wait_for_timeout(400)

        guide_body_visible_after = await page.evaluate("""() => {
            const body = document.getElementById('ytGuideBody');
            return body && window.getComputedStyle(body).display !== 'none';
        }""")
        assert guide_body_visible_after, "Guide body should expand after clicking toggle"
        print("    Guide body expanded successfully with step-by-step instructions.")

        # Test Stream Key eye toggle
        print("[5] Testing Stream Key Input and Eye Toggle...")
        key_input = await page.query_selector("#ytStreamKey")
        assert key_input is not None, "Stream Key input not found"
        await key_input.fill("live_12345678_abcdefghijk")

        type_before = await page.evaluate("() => document.getElementById('ytStreamKey').type")
        assert type_before == "password", f"Expected type password, got {type_before}"

        btn_eye = await page.query_selector("#btnToggleYtKeyEye")
        await btn_eye.click()
        await page.wait_for_timeout(200)

        type_after = await page.evaluate("() => document.getElementById('ytStreamKey').type")
        assert type_after == "text", f"Expected type text after toggle, got {type_after}"

        # Toggle back to password
        await btn_eye.click()
        await page.wait_for_timeout(200)
        assert await page.evaluate("() => document.getElementById('ytStreamKey').type") == "password"
        print("    Eye visibility toggle functioning correctly.")

        # Test changing lens and quality options
        print("[6] Setting stream options...")
        await page.select_option("#ytLensSelect", "left")
        await page.select_option("#ytQualitySelect", "native")

        # Capture screenshot with modal open and blurred video
        screenshot_dir = "/root/cctv_dashboard/docs/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        modal_screenshot_path = os.path.join(screenshot_dir, "youtube_preview.png")
        await page.screenshot(path=modal_screenshot_path)
        print(f"[7] Screenshot saved to: {modal_screenshot_path}")

        # Close modal
        print("[8] Closing YouTube modal...")
        await page.evaluate("() => closeYouTubeModal()")
        await page.wait_for_timeout(400)
        modal_closed = await page.evaluate("""() => {
            const m = document.getElementById('youtubeModal');
            return !m.classList.contains('open');
        }""")
        assert modal_closed, "YouTube modal did not close"
        print("    YouTube modal closed successfully.")

        await browser.close()
        print("[9] All YouTube streaming UI and API tests PASSED.")

if __name__ == "__main__":
    asyncio.run(run())
