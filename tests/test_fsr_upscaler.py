import asyncio
import os
from playwright.async_api import async_playwright

async def run_fsr_unit_test():
    script_path = os.path.abspath("/root/cctv_dashboard/public/fsr-upscaler.js")
    with open(script_path, "r") as f:
        fsr_code = f.read()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        page = await browser.new_page()

        # Inject HTML and run the tests in browser context
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>FSR Unit Test</title></head>
        <body>
            <video id="testVideo" width="640" height="360" autoplay playsinline muted></video>
            <canvas id="testCanvas" width="640" height="360"></canvas>
            <script>
            {fsr_code}
            </script>
        </body>
        </html>
        """
        await page.set_content(html_content)

        test_result = await page.evaluate("""async () => {
            const results = [];
            const video = document.getElementById('testVideo');
            const canvas = document.getElementById('testCanvas');

            // Test 1: Class defined
            if (typeof window.FsrUpscaler !== 'function') {
                return { success: false, error: 'FsrUpscaler is not defined on window' };
            }
            results.push('Test 1: FsrUpscaler is defined');

            // Draw a test pattern on an offscreen canvas and pipe to video if needed, or use a simulated readyState
            const upscaler = new window.FsrUpscaler(video, canvas, { sharpness: 0.2 });

            // Test 2: init()
            const initSuccess = upscaler.init();
            if (!initSuccess) {
                return { success: false, error: 'FsrUpscaler.init() failed' };
            }
            results.push('Test 2: FsrUpscaler.init() returned true, shaders compiled and linked');

            // Test 3: setCrop()
            upscaler.setCrop(2.5, 50, -30, 640, 360);
            if (!Array.isArray(upscaler.cropMin) || !Array.isArray(upscaler.cropMax)) {
                return { success: false, error: 'setCrop failed to update cropMin/cropMax' };
            }
            results.push(`Test 3: setCrop calculated [${upscaler.cropMin}] to [${upscaler.cropMax}]`);

            // Test 4: setSharpness()
            upscaler.setSharpness(0.5);
            if (upscaler.sharpness !== 0.5) {
                return { success: false, error: 'setSharpness failed' };
            }
            results.push('Test 4: setSharpness updated to 0.5');

            // Test 5: Mock video texture & render with vertical orientation assertion
            const mockCanvas = document.createElement('canvas');
            mockCanvas.width = 640;
            mockCanvas.height = 360;
            const ctx = mockCanvas.getContext('2d');
            // Top half is RED, Bottom half is BLUE
            ctx.fillStyle = '#ff0000';
            ctx.fillRect(0, 0, 640, 180);
            ctx.fillStyle = '#0000ff';
            ctx.fillRect(0, 180, 640, 180);

            // Back video element with mockCanvas for render test
            upscaler.video = mockCanvas;
            mockCanvas.readyState = 4;
            mockCanvas.videoWidth = 640;
            mockCanvas.videoHeight = 360;

            upscaler.setCrop(1.0, 0, 0, 640, 360);
            upscaler.render();

            // Sample top and bottom pixels
            const gl = upscaler.gl;
            const topPix = new Uint8Array(4);
            const btmPix = new Uint8Array(4);
            gl.readPixels(320, upscaler.canvas.height - 10, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, topPix);
            gl.readPixels(320, 10, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, btmPix);

            const topIsRed = topPix[0] > 200 && topPix[2] < 50;
            const btmIsBlue = btmPix[2] > 200 && btmPix[0] < 50;
            if (!topIsRed || !btmIsBlue) {
                return {
                    success: false,
                    error: `Orientation inverted: top=[${topPix}], bottom=[${btmPix}]. Expected top=Red, bottom=Blue.`
                };
            }
            results.push('Test 5: render() executed with verified RIGHT-SIDE-UP vertical orientation (top=Red, bottom=Blue)');

            // Test 6: captureSnapshot()
            let snapshotBlob = null;
            try {
                snapshotBlob = await upscaler.captureSnapshot('image/jpeg', 0.95);
            } catch(e) {
                return { success: false, error: 'captureSnapshot threw: ' + e.message };
            }
            if (!snapshotBlob || snapshotBlob.size === 0) {
                return { success: false, error: 'captureSnapshot returned empty blob' };
            }
            results.push(`Test 6: captureSnapshot generated JPEG Blob (${snapshotBlob.size} bytes)`);

            // Test 7: destroy()
            upscaler.destroy();
            if (upscaler.gl !== null) {
                return { success: false, error: 'destroy() did not nullify gl' };
            }
            results.push('Test 7: destroy() cleaned up resources');

            return { success: true, results };
        }""")

        await browser.close()
        return test_result

if __name__ == "__main__":
    result = asyncio.run(run_fsr_unit_test())
    print("Test Result Success:", result.get("success"))
    if not result.get("success"):
        print("Error:", result.get("error"))
    else:
        for r in result.get("results", []):
            print("  -", r)
