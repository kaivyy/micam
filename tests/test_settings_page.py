import asyncio
import os
import shutil
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = "/root/cctv_dashboard/docs/screenshots"
ARTIFACTS_DIR = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739"

async def run():
    print("[1] Starting Playwright E2E tests for Advanced Camera Settings & SD Card Management...")
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # -------------------------------------------------------------
        # TEST 1: DESKTOP SETTINGS PAGE & REAL HARDWARE DATA
        # -------------------------------------------------------------
        print("\n--- TEST 1: Desktop Settings Page (1440x900) ---")
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1
        )
        page = await context.new_page()

        print("[Desktop] Navigating to http://127.0.0.1:8088/settings...")
        await page.goto("http://127.0.0.1:8088/settings", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Check title
        title = await page.title()
        print(f"[Desktop] Page title: {title}")
        assert "Setelan Hardware Kamera" in title, f"Unexpected title: {title}"

        # Check all 4 cards exist
        card_titles = await page.eval_on_selector_all(".card-title", "els => els.map(e => e.textContent.trim())")
        print(f"[Desktop] Cards detected: {card_titles}")
        assert "Tampilan & Optik Kamera" in card_titles
        assert "Lampu & Audio Hardware" in card_titles
        assert "Sensitivitas AI & Keamanan" in card_titles
        assert "Manajemen Kartu MicroSD Fisik" in card_titles

        # Check real SD card status
        sd_status = await page.text_content("#sdStatusText")
        sd_total = await page.text_content("#sdTotalText")
        sd_used = await page.text_content("#sdUsedText")
        print(f"[Desktop] SD Card: Status='{sd_status}', Total='{sd_total}', Used='{sd_used}'")
        assert sd_status in ["Normal", "Tidak Terdeteksi", "Penyimpanan Penuh"]

        # Test toggle change and toast notification
        print("[Desktop] Testing toggle change (distortion correction)...")
        toggle_checked_before = await page.is_checked("#prop_distortion_correction")
        await page.click("label:has(#prop_distortion_correction)")
        await page.wait_for_timeout(600)

        # Check toast
        toast_text = await page.text_content(".toast")
        print(f"[Desktop] Toast notification received: '{toast_text}'")
        assert "distortion correction" in toast_text.lower() or "berhasil" in toast_text.lower()

        # Revert toggle
        await page.click("label:has(#prop_distortion_correction)")
        await page.wait_for_timeout(600)

        # Capture Desktop Screenshot
        desktop_img_path = os.path.join(SCREENSHOTS_DIR, "settings_desktop.png")
        await page.screenshot(path=desktop_img_path, full_page=True)
        print(f"[Desktop] Screenshot saved to: {desktop_img_path}")
        shutil.copy(desktop_img_path, os.path.join(ARTIFACTS_DIR, "settings_desktop.png"))

        # Test "Kembali ke Live Monitor" back button
        print("[Desktop] Testing 'Kembali ke Live Monitor' button...")
        await page.click("a.btn-nav:has-text('Kembali ke Live Monitor')")
        await page.wait_for_timeout(1000)
        curr_url = page.url
        print(f"[Desktop] Current URL after back button: {curr_url}")
        assert curr_url.endswith(":8088/") or curr_url.endswith(":8088"), f"Expected home URL, got: {curr_url}"
        await context.close()

        # -------------------------------------------------------------
        # TEST 2: MOBILE VIEWPORT & DRAWER NAVIGATION (390x844)
        # -------------------------------------------------------------
        print("\n--- TEST 2: Mobile Viewport & Drawer Navigation (390x844) ---")
        mobile_context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True
        )
        mobile_page = await mobile_context.new_page()

        print("[Mobile] Navigating to http://127.0.0.1:8088/...")
        await mobile_page.goto("http://127.0.0.1:8088", wait_until="domcontentloaded")
        await mobile_page.wait_for_timeout(1500)

        # Close any setup wizard if open
        await mobile_page.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.classList.remove('open');
        }""")

        # Open mobile drawer
        print("[Mobile] Opening mobile drawer menu...")
        await mobile_page.click("button.bottom-nav-item:has-text('Menu')")
        await mobile_page.wait_for_timeout(500)

        drawer_active = await mobile_page.evaluate("() => document.getElementById('mobileDrawer').classList.contains('active')")
        assert drawer_active, "Mobile drawer is not active"

        # Check 'Setelan Hardware Kamera' item in drawer
        drawer_settings_item = await mobile_page.query_selector("a.drawer-menu-item:has-text('Setelan Hardware Kamera')")
        assert drawer_settings_item is not None, "Settings item missing from mobile drawer"

        # Click the settings item in drawer
        print("[Mobile] Clicking 'Setelan Hardware Kamera' in mobile drawer...")
        await drawer_settings_item.click()
        await mobile_page.wait_for_timeout(1200)

        assert "settings" in mobile_page.url, f"Expected navigation to /settings, got: {mobile_page.url}"

        # Capture Mobile Screenshot
        mobile_img_path = os.path.join(SCREENSHOTS_DIR, "settings_mobile.png")
        await mobile_page.screenshot(path=mobile_img_path, full_page=True)
        print(f"[Mobile] Screenshot saved to: {mobile_img_path}")
        shutil.copy(mobile_img_path, os.path.join(ARTIFACTS_DIR, "settings_mobile.png"))

        await mobile_context.close()

        # -------------------------------------------------------------
        # TEST 3: AUTH GATING (UNAUTHENTICATED ACCESS LOCK)
        # -------------------------------------------------------------
        print("\n--- TEST 3: Auth Gating Verification (Unauthenticated Lock) ---")
        unauth_context = await browser.new_context(viewport={"width": 1280, "height": 800})
        unauth_page = await unauth_context.new_page()

        # Mock /api/camera/advanced to return 401 Unauthorized
        await unauth_page.route("**/api/camera/advanced", lambda route: route.fulfill(
            status=401,
            content_type="application/json",
            body='{"success": false, "authenticated": false, "error": "Autentikasi akun Xiaomi diperlukan"}'
        ))

        print("[Auth Gate] Navigating to /settings with simulated 401 Unauthorized...")
        await unauth_page.goto("http://127.0.0.1:8088/settings", wait_until="domcontentloaded")
        await unauth_page.wait_for_timeout(800)

        # Verify auth gate card is VISIBLE
        auth_card_visible = await unauth_page.evaluate("""() => {
            const card = document.getElementById('authGateCard');
            return card && window.getComputedStyle(card).display !== 'none';
        }""")
        print(f"[Auth Gate] Auth card visible: {auth_card_visible}")
        assert auth_card_visible, "Auth gate card should be displayed when user is unauthenticated!"

        # Verify settings grid is HIDDEN
        settings_grid_hidden = await unauth_page.evaluate("""() => {
            const grid = document.getElementById('settingsContainer');
            return !grid || window.getComputedStyle(grid).display === 'none';
        }""")
        print(f"[Auth Gate] Settings grid hidden: {settings_grid_hidden}")
        assert settings_grid_hidden, "Settings grid should be hidden when user is unauthenticated!"

        # Capture Auth Gate Screenshot
        auth_img_path = os.path.join(SCREENSHOTS_DIR, "settings_auth_gate.png")
        await unauth_page.screenshot(path=auth_img_path)
        print(f"[Auth Gate] Screenshot saved to: {auth_img_path}")
        shutil.copy(auth_img_path, os.path.join(ARTIFACTS_DIR, "settings_auth_gate.png"))

        await unauth_context.close()
        await browser.close()

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    asyncio.run(run())
