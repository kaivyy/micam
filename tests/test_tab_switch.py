#!/usr/bin/env python3
"""
E2E test for tab switching behaviour.
Verifies:
1. A short tab switch (inside the grace period) keeps both streams connected.
2. A long absence releases the camera sessions and holds the last frame.
3. Returning reconnects both lenses and clears the held frame.
"""
import io
import json
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8088"

SET_VISIBILITY = """(hidden) => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
    Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => hidden ? 'hidden' : 'visible'});
    document.dispatchEvent(new Event('visibilitychange'));
}"""

LENS_STATE = """() => ['camLeft', 'camRight'].map(id => {
    const el = document.getElementById(id);
    const v = el.video;
    return {
        id,
        ws: el.wsState,
        ready: v ? v.readyState : -1,
        width: v ? v.videoWidth : 0,
        poster: v ? (v.getAttribute('poster') || '').slice(0, 11) : '',
        holding: el.classList.contains('cam-reconnecting')
    };
})"""


def _standby_off():
    req = urllib.request.Request(
        f"{BASE}/api/streams/standby",
        data=json.dumps({"standby": False}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5).read()


def _wait_playing(page, timeout_ms=20000):
    page.wait_for_function(
        "() => ['camLeft','camRight'].every(id => { const v = document.getElementById(id).video; return v && v.readyState >= 2; })",
        timeout=timeout_ms,
    )


def test_tab_switch_grace_and_frame_hold():
    _standby_off()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate(
            """() => {
                const w = document.getElementById('setupWizardModal'); if (w) w.style.display = 'none';
                const b = document.getElementById('wizardBackdrop'); if (b) b.style.display = 'none';
            }"""
        )
        _wait_playing(page)
        print("[1] Both lenses playing.")

        page.evaluate(SET_VISIBILITY, True)
        page.wait_for_timeout(3000)
        states = page.evaluate(LENS_STATE)
        print(f"[2] Hidden 3s: {states}")
        assert all(s["ws"] == 1 for s in states), "Streams must stay connected during the grace period"
        assert all(not s["holding"] for s in states), "No frame hold inside the grace period"

        page.evaluate(SET_VISIBILITY, False)
        page.wait_for_timeout(1500)
        states = page.evaluate(LENS_STATE)
        print(f"[3] Back inside grace: {states}")
        assert all(s["ws"] == 1 and s["ready"] >= 2 for s in states), "Streams must be intact after a short switch"

        page.evaluate(SET_VISIBILITY, True)
        page.wait_for_timeout(31500)
        states = page.evaluate(LENS_STATE)
        print(f"[4] Hidden 31s: {states}")
        assert all(s["ws"] == 3 for s in states), "Streams must be released after the grace period"
        for s in states:
            if s["width"]:
                assert s["holding"] and s["poster"] == "data:image/", "Last frame must be held"
            else:
                print(f"    {s['id']}: no decoded video track in this browser, frame hold checked separately")

        page.evaluate(SET_VISIBILITY, False)
        _wait_playing(page)
        page.wait_for_timeout(1200)
        states = page.evaluate(LENS_STATE)
        print(f"[5] Returned: {states}")
        assert all(s["ws"] == 1 and s["ready"] >= 2 for s in states), "Both lenses must reconnect"
        assert all(not s["holding"] and s["poster"] == "" for s in states), "Held frame must clear once playing"

        # Headless Chromium cannot decode H.265, so exercise the frame hold path
        # with a synthetic canvas video source.
        held = page.evaluate(
            """async () => {
                const el = document.getElementById('camLeft');
                el.ondisconnect();
                const c = document.createElement('canvas');
                c.width = 640; c.height = 360;
                const ctx = c.getContext('2d');
                const paint = () => { ctx.fillStyle = '#dd3333'; ctx.fillRect(0, 0, 640, 360); };
                paint();
                const timer = setInterval(paint, 100);
                el.video.srcObject = c.captureStream(10);
                await el.video.play();
                for (let i = 0; i < 50 && !el.video.videoWidth; i++) await new Promise(r => setTimeout(r, 100));
                disconnectStreams(true);
                clearInterval(timer);
                return {width: el.video.videoWidth, poster: (el.video.getAttribute('poster') || '').slice(0, 11),
                        holding: el.classList.contains('cam-reconnecting')};
            }"""
        )
        print(f"[6] Synthetic frame hold: {held}")
        assert held["poster"] == "data:image/" and held["holding"], "Synthetic frame must be held after disconnect"

        page.wait_for_timeout(500)
        from PIL import Image
        shot = Image.open(io.BytesIO(page.locator("#camLeft").screenshot())).convert("RGB")
        r, g, b = shot.resize((1, 1)).getpixel((0, 0))
        print(f"[7] Held frame average colour (R,G,B): {r:.0f},{g:.0f},{b:.0f}")
        assert r > 60 and r > g * 1.5, "Held frame must be visible instead of a black screen"

        page.evaluate("() => reconnectStreams()")
        _wait_playing(page)
        page.wait_for_timeout(1200)
        states = page.evaluate(LENS_STATE)
        print(f"[8] Reconnected: {states}")
        assert all(not s["holding"] and s["poster"] == "" for s in states), "Held frame must clear after reconnect"

        browser.close()
        print("[9] Tab switch grace period and frame hold tests PASSED.")


if __name__ == "__main__":
    test_tab_switch_grace_and_frame_hold()
