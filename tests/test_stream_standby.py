#!/usr/bin/env python3
"""
E2E Test for Camera Stream Release, Standby Mode, and Idle Watchdog
Verifies:
1. Desktop: Bebaskan Kamera (Standby) toggle and overlay display
2. Desktop: Idle timeout configuration persistence
3. Mobile: Default single-lens mode (< 640px) to preserve P2P slots
4. Mobile Drawer: Bebaskan Kamera menu item
5. Backend: POST /api/streams/release instant teardown
"""
import urllib.request
import json
import time
from playwright.sync_api import sync_playwright

def test_stream_release_api():
    print("[API] Testing POST /api/streams/release...")
    req = urllib.request.Request("http://127.0.0.1:8088/api/streams/release", data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = json.loads(res.read().decode())
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"[API] Success: {data.get('message')}")

def test_frontend_standby_and_idle():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Desktop Viewport
        print("\n--- TEST 1: Desktop Viewport (1280x800) ---")
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto("http://127.0.0.1:8088", wait_until="networkidle")

        # Verify button and idle select exist
        btn_standby = page.locator("#btnToggleStandby")
        assert btn_standby.is_visible(), "Button Bebaskan Kamera must be visible on desktop"
        txt_standby = page.locator("#txtStandbyState").inner_text()
        assert "Bebaskan Kamera" in txt_standby, f"Expected 'Bebaskan Kamera', got '{txt_standby}'"

        select_idle = page.locator("#selectIdleTimeout")
        assert select_idle.is_visible(), "Idle timeout select must be visible on desktop"
        val_idle = select_idle.input_value()
        assert val_idle in ["5", "10", "30", "0"], f"Invalid idle timeout default value: {val_idle}"
        print(f"[Desktop] Initial standby button: '{txt_standby}', idle timeout: '{val_idle}' min")

        # Click Bebaskan Kamera -> Standby active
        print("[Desktop] Clicking 'Bebaskan Kamera' to enter standby...")
        btn_standby.click()
        page.wait_for_timeout(300)

        txt_standby_after = page.locator("#txtStandbyState").inner_text()
        assert "Lanjutkan Live" in txt_standby_after, f"Expected 'Lanjutkan Live', got '{txt_standby_after}'"

        overlay_left = page.locator("#standbyOverlay_camLeft")
        assert overlay_left.is_visible(), "Overlay left must be visible in standby mode"
        print("[Desktop] Standby overlay confirmed visible.")

        # Click 'Lanjutkan Live' button inside overlay to resume
        print("[Desktop] Clicking 'Lanjutkan Live' button on overlay...")
        resume_btn = overlay_left.locator("button:has-text('Lanjutkan Live')")
        resume_btn.click()
        page.wait_for_timeout(300)

        assert not overlay_left.is_visible(), "Overlay left must be hidden after resuming"
        txt_resumed = page.locator("#txtStandbyState").inner_text()
        assert "Bebaskan Kamera" in txt_resumed, f"Expected 'Bebaskan Kamera', got '{txt_resumed}'"
        print("[Desktop] Live stream resumed successfully.")

        # Test changing idle timeout setting
        print("[Desktop] Setting idle timeout to 5 minutes...")
        select_idle.select_option("5")
        page.wait_for_timeout(200)
        stored_timeout = page.evaluate("() => localStorage.getItem('cctv_idle_timeout')")
        assert stored_timeout == "5", f"Expected localStorage 5, got {stored_timeout}"
        print(f"[Desktop] Stored idle timeout verified: {stored_timeout} min")

        context.close()

        # 2. Mobile Viewport
        print("\n--- TEST 2: Mobile Viewport (390x844) ---")
        context_mobile = browser.new_context(viewport={"width": 390, "height": 844})
        page_mobile = context_mobile.new_page()
        page_mobile.goto("http://127.0.0.1:8088", wait_until="networkidle")

        # Check that on mobile it defaults to single lens (left) to conserve camera slots
        current_lens = page_mobile.evaluate("() => currentLensView")
        print(f"[Mobile] Auto-detected lens view mode: '{current_lens}'")
        assert current_lens == "left", f"Expected mobile default 'left', got '{current_lens}'"

        mon_left = page_mobile.locator("#monBoxLeft")
        mon_right = page_mobile.locator("#monBoxRight")
        assert mon_left.is_visible(), "Lensa Kiri must be visible on mobile"
        assert not mon_right.is_visible(), "Lensa Kanan must be hidden on mobile default single-lens"
        print("[Mobile] Single lens confirmed active (conserves 1 P2P channel).")

        # Check mobile drawer has 'Bebaskan Kamera'
        print("[Mobile] Opening mobile drawer menu...")
        page_mobile.evaluate("""() => {
            const w = document.getElementById('setupWizardModal');
            if (w) w.classList.remove('open');
        }""")
        page_mobile.locator("button.bottom-nav-item:has-text('Menu')").click()
        page_mobile.wait_for_timeout(300)

        drawer_standby = page_mobile.locator("#drawerTxtStandbyState")
        assert drawer_standby.is_visible(), "Drawer item 'Bebaskan Kamera' must be visible in drawer"
        print(f"[Mobile] Drawer item found: '{drawer_standby.inner_text()}'")

        # Click drawer standby button
        drawer_standby_btn = page_mobile.locator("button.drawer-menu-item:has(#drawerTxtStandbyState)")
        drawer_standby_btn.click()
        page_mobile.wait_for_timeout(400)

        # Verify drawer closed and standby overlay visible
        overlay_left_mobile = page_mobile.locator("#standbyOverlay_camLeft")
        assert overlay_left_mobile.is_visible(), "Mobile standby overlay must be visible after drawer click"
        print("[Mobile] Standby successfully engaged from drawer.")

        # Resume stream on mobile
        overlay_left_mobile.locator("button:has-text('Lanjutkan Live')").click()
        page_mobile.wait_for_timeout(300)
        assert not overlay_left_mobile.is_visible(), "Mobile standby overlay must be hidden after resuming"
        print("[Mobile] Stream resumed successfully.")

        context_mobile.close()
        browser.close()

if __name__ == "__main__":
    test_stream_release_api()
    test_frontend_standby_and_idle()
    print("\n[SUCCESS] All stream release, standby mode, and mobile optimization tests PASSED!")
