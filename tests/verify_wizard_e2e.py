#!/usr/bin/env python3
"""
Playwright End-to-End Verification for Web Setup Wizard & Adaptive Lens UI
Tests Desktop and Mobile viewports, modal interactions, and console hygiene.
"""

import os
import sys
import asyncio
from playwright.async_api import async_playwright

DASHBOARD_URL = "http://127.0.0.1:8088"
ARTIFACT_DIR = "/root/.gemini/antigravity-cli/brain/4217dc17-e6a3-4669-a836-b6a86fda8739"


async def run_e2e_tests():
    console_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        # -------------------------------------------------------------
        # 1. Desktop Viewport Test (1920x1080)
        # -------------------------------------------------------------
        print("\n--- 1. Testing Setup Wizard on Desktop (1920x1080) ---")
        context_desktop = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context_desktop.new_page()

        def handle_console(msg):
            if msg.type == "error":
                print(f"  [Console Error]: {msg.text}")
                console_errors.append(msg.text)
            else:
                print(f"  [Console {msg.type}]: {msg.text}")

        page.on("console", handle_console)
        await page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1000)

        # Click Setup Wizard button in Navbar
        wizard_btn = page.locator("#btnOpenWizardModal")
        assert await wizard_btn.is_visible(), "Setup CCTV button should be visible in desktop navbar"
        await wizard_btn.click()
        await page.wait_for_timeout(1500)

        # Assert Wizard modal is open
        wizard_modal = page.locator("#setupWizardModal")
        modal_class = await wizard_modal.get_attribute("class") or ""
        assert "open" in modal_class, "Setup Wizard modal should have 'open' class"
        assert await page.locator("#wizNode1").is_visible(), "Step 1 node should be visible"

        # Verify direct link generated
        direct_link = page.locator("#wizDirectLink")
        assert await direct_link.is_visible(), "Direct verification link should be visible"
        link_href = await direct_link.get_attribute("href") or ""
        assert "account.xiaomi.com" in link_href, f"Direct link should point to Xiaomi SSO, got: {link_href}"

        # Pause countdown DOM mutation momentarily to ensure stable screenshot capture
        await page.evaluate("clearInterval(wizardCountdownInterval)")
        desktop_screenshot = os.path.join(ARTIFACT_DIR, "setup_wizard_desktop.png")
        await page.screenshot(path=desktop_screenshot)
        print(f"  [PASSED] Desktop screenshot saved to: {desktop_screenshot}")

        # Test Adaptive Lens Mode (Single vs Dual)
        print("\n--- 2. Testing Adaptive Lens Mode (Single vs Dual) ---")
        await page.evaluate("applyLensMode('single')")
        await page.wait_for_timeout(500)
        right_box_display = await page.evaluate("document.getElementById('monBoxRight').style.display")
        left_grid_col = await page.evaluate("document.getElementById('monBoxLeft').style.gridColumn")
        assert right_box_display == "none", f"Right lens should be hidden in single mode, got: {right_box_display}"
        assert "1 / -1" in left_grid_col, f"Left lens should span full width in single mode, got: {left_grid_col}"
        print("  [PASSED] Single-lens layout correctly hid secondary lens and expanded primary lens to full width.")

        # Re-enable dual mode
        await page.evaluate("applyLensMode('dual')")
        await page.wait_for_timeout(500)
        right_box_display_restored = await page.evaluate("document.getElementById('monBoxRight').style.display")
        assert right_box_display_restored == "", f"Right lens should be restored in dual mode, got: {right_box_display_restored}"
        print("  [PASSED] Dual-lens layout correctly restored.")

        await context_desktop.close()

        # -------------------------------------------------------------
        # 3. Mobile Viewport Test (390x844 - iPhone 14 / Mobile standard)
        # -------------------------------------------------------------
        print("\n--- 3. Testing Setup Wizard on Mobile (390x844) ---")
        context_mobile = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
        )
        page_m = await context_mobile.new_page()
        page_m.on("console", handle_console)
        await page_m.goto(DASHBOARD_URL, wait_until="networkidle", timeout=15000)

        # Open Setup Wizard on mobile
        await page_m.evaluate("openSetupWizard()")
        await page_m.wait_for_timeout(1500)

        # Verify modal fits mobile screen without overflowing
        modal_box = await page_m.locator("#setupWizardModal .wizard-card").bounding_box()
        assert modal_box is not None, "Wizard card bounding box should be present"
        assert modal_box["width"] <= 390, f"Wizard card width ({modal_box['width']}px) should fit within mobile screen width 390px"

        await page_m.evaluate("clearInterval(wizardCountdownInterval)")
        mobile_screenshot = os.path.join(ARTIFACT_DIR, "setup_wizard_mobile.png")
        await page_m.screenshot(path=mobile_screenshot)
        print(f"  [PASSED] Mobile screenshot saved to: {mobile_screenshot}")

        await context_mobile.close()
        await browser.close()

    filtered_errors = [e for e in console_errors if "favicon" not in e.lower() and "failed to fetch" not in e.lower()]
    assert len(filtered_errors) == 0, f"Encountered unexpected console errors: {filtered_errors}"
    print("\n[ALL E2E VERIFICATION TESTS PASSED SUCCESSFULLY WITH 0 CONSOLE ERRORS!]")


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
