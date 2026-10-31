import asyncio
import os
from playwright.async_api import async_playwright

async def run():
    print("[1] Starting Playwright tests for Login QR Bug & Responsive YouTube Dropdowns...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # -------------------------------------------------------------
        # TEST 1: DESKTOP & SETUP WIZARD (LOGGED IN STATE VERIFICATION)
        # -------------------------------------------------------------
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1
        )
        page = await context.new_page()

        print("[2] Navigating to http://127.0.0.1:8088 on desktop...")
        await page.goto("http://127.0.0.1:8088", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Blur video elements for privacy
        await page.evaluate("""() => {
            document.querySelectorAll('video, canvas, .video-player-wrapper').forEach(el => {
                el.style.filter = 'blur(16px)';
            });
        }""")

        # Close any setup wizard if already opened on startup
        await page.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.classList.remove('open');
        }""")
        await page.wait_for_timeout(300)

        # Click "Setup CCTV" in header
        print("[3] Clicking 'Setup CCTV' button to test wizard while logged in...")
        await page.click("#btnOpenWizardModal")
        await page.wait_for_timeout(600)

        # Verify wizard modal is open
        wiz_open = await page.evaluate("() => document.getElementById('setupWizardModal').classList.contains('open')")
        assert wiz_open, "Setup Wizard did not open"

        # Check logged-in view is visible
        logged_in_visible = await page.evaluate("""() => {
            const el = document.getElementById('wizStep1LoggedIn');
            return el && window.getComputedStyle(el).display !== 'none';
        }""")
        assert logged_in_visible, "wizStep1LoggedIn should be VISIBLE when user is logged in"

        # Check QR box and direct login link DO NOT APPEAR
        qr_unauth_visible = await page.evaluate("""() => {
            const el = document.getElementById('wizStep1Unauthenticated');
            return el && window.getComputedStyle(el).display !== 'none';
        }""")
        assert not qr_unauth_visible, "wizStep1Unauthenticated (QR box & login link) MUST NOT appear when logged in!"

        qr_img_visible = await page.evaluate("""() => {
            const img = document.getElementById('wizQrImage');
            return img && window.getComputedStyle(img).display !== 'none';
        }""")
        assert not qr_img_visible, "QR Image MUST NOT appear when logged in!"

        direct_link_visible = await page.evaluate("""() => {
            const a = document.getElementById('wizDirectLink');
            return a && window.getComputedStyle(a).display !== 'none';
        }""")
        assert not direct_link_visible, "Direct login link MUST NOT appear when logged in!"
        print("    SUCCESS: When logged in, QR Code and Login Link DO NOT appear!")

        # Test proceeding to step 2 (pilihan kamera)
        print("[4] Testing proceeding to Camera Selection (Step 2)...")
        await page.evaluate("() => proceedToCameraSelection()")
        await page.wait_for_timeout(800)

        step2_visible = await page.evaluate("""() => {
            const b = document.getElementById('wizStep2Body');
            return b && window.getComputedStyle(b).display !== 'none';
        }""")
        assert step2_visible, "Step 2 should be visible after clicking proceed"

        camera_cards_count = await page.evaluate("() => document.querySelectorAll('#wizCameraList .camera-card-item').length")
        print(f"    Discovered cameras in Step 2: {camera_cards_count}")
        assert camera_cards_count >= 1, "Configured camera card should be displayed in Step 2"

        # Close wizard
        await page.evaluate("() => closeSetupWizard()")
        await page.wait_for_timeout(400)

        # -------------------------------------------------------------
        # TEST 2: YOUTUBE MODAL DROPDOWNS ON DESKTOP
        # -------------------------------------------------------------
        print("[5] Testing YouTube Modal Dropdowns on Desktop...")
        await page.click("#btnOpenYouTubeModal")
        await page.wait_for_timeout(500)

        yt_modal_open = await page.evaluate("() => document.getElementById('youtubeModal').classList.contains('open')")
        assert yt_modal_open, "YouTube modal did not open"

        # Check form-select styles
        lens_styles = await page.evaluate("""() => {
            const sel = document.getElementById('ytLensSelect');
            const style = window.getComputedStyle(sel);
            return {
                minHeight: style.minHeight,
                color: style.color,
                backgroundColor: style.backgroundColor,
                appearance: style.appearance,
                borderRadius: style.borderRadius
            };
        }""")
        print(f"    Desktop .form-select computed styles: {lens_styles}")
        assert "42px" in lens_styles["minHeight"] or int(lens_styles["minHeight"].replace("px", "")) >= 40, "Dropdown min-height must be >= 40px"

        # Check 2-column layout on desktop
        grid_cols_desktop = await page.evaluate("""() => {
            const grid = document.querySelector('.yt-options-grid');
            return window.getComputedStyle(grid).gridTemplateColumns;
        }""")
        print(f"    Desktop .yt-options-grid columns: {grid_cols_desktop}")
        # On desktop it has 2 columns
        assert len(grid_cols_desktop.split()) == 2, f"Expected 2 columns on desktop, got {grid_cols_desktop}"

        # Capture desktop preview with YouTube modal
        desktop_yt_img = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739/youtube_modal_desktop.png"
        await page.screenshot(path=desktop_yt_img)
        print(f"    Saved desktop screenshot to: {desktop_yt_img}")

        await page.evaluate("() => closeYouTubeModal()")
        await page.wait_for_timeout(300)
        await context.close()

        # -------------------------------------------------------------
        # TEST 3: MOBILE RESPONSIVENESS OF YOUTUBE DROPDOWNS (375x667)
        # -------------------------------------------------------------
        print("[6] Testing YouTube Modal Dropdowns on Mobile Viewport (375x667 iPhone SE)...")
        mobile_context = await browser.new_context(
            viewport={"width": 375, "height": 667},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True
        )
        mobile_page = await mobile_context.new_page()
        await mobile_page.goto("http://127.0.0.1:8088", wait_until="domcontentloaded")
        await mobile_page.wait_for_timeout(2000)

        # Blur video for privacy
        await mobile_page.evaluate("""() => {
            document.querySelectorAll('video, canvas, .video-player-wrapper').forEach(el => {
                el.style.filter = 'blur(16px)';
            });
            const w = document.getElementById('setupWizardModal');
            if (w) w.classList.remove('open');
        }""")

        # Open YouTube modal on mobile
        await mobile_page.evaluate("() => openYouTubeModal()")
        await mobile_page.wait_for_timeout(600)

        # Check 1-column layout on mobile
        grid_cols_mobile = await mobile_page.evaluate("""() => {
            const grid = document.querySelector('.yt-options-grid');
            return window.getComputedStyle(grid).gridTemplateColumns;
        }""")
        print(f"    Mobile .yt-options-grid columns: {grid_cols_mobile}")
        assert len(grid_cols_mobile.split()) == 1, f"Expected 1 stacked column on mobile, got {grid_cols_mobile}"

        # Check bounding boxes of dropdowns to ensure no overflow
        mobile_box = await mobile_page.evaluate("""() => {
            const sel1 = document.getElementById('ytLensSelect');
            const sel2 = document.getElementById('ytQualitySelect');
            const r1 = sel1.getBoundingClientRect();
            const r2 = sel2.getBoundingClientRect();
            return {
                w1: r1.width,
                w2: r2.width,
                overflowRight1: r1.right > window.innerWidth,
                overflowRight2: r2.right > window.innerWidth,
                windowWidth: window.innerWidth
            };
        }""")
        print(f"    Mobile dropdown metrics: {mobile_box}")
        assert not mobile_box["overflowRight1"], f"Lens select overflows mobile screen: {mobile_box}"
        assert not mobile_box["overflowRight2"], f"Quality select overflows mobile screen: {mobile_box}"
        assert mobile_box["w1"] > 250, "Dropdown should take full available card width on mobile"

        # Capture mobile screenshot
        mobile_yt_img = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739/youtube_modal_mobile.png"
        await mobile_page.screenshot(path=mobile_yt_img)
        print(f"    Saved mobile screenshot to: {mobile_yt_img}")

        await mobile_context.close()
        await browser.close()
        print("[7] All Login QR Bug and Responsive YouTube Dropdown tests PASSED.")

if __name__ == "__main__":
    asyncio.run(run())
