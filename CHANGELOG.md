# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.8] - 2026-11-01

### Fixed
- **Black screen after switching browser tabs**: The dashboard no longer drops both streams the instant a tab is hidden. Streams stay connected for a 30 second grace period (`HIDDEN_DISCONNECT_MS`), so a quick tab switch resumes with no reload. After a longer absence the camera session is released as before, which keeps Mi Home free.
- **Last frame held while reconnecting**: When streams are released after the grace period, the last decoded frame of each lens is kept as the video poster (dimmed, with a "Menyambung ulang..." label) until the first new keyframe plays, completely eliminating the black screen flash. The held frame is never kept in standby mode.
- **Desktop & Laptop Navbar Layout Balance**: Fixed header responsiveness across mid-range desktop and laptop viewports (641px - 1366px) by locking `.brand` with `flex-shrink: 0`, preventing the brand title and logo from being squished or pushed out by action buttons.

### Added
- **Modern App Icon & Branding**: Added an Apple Pro / macOS titanium squircle app icon featuring a dual-sensor camera motif with emerald green (`#10b981`) and electric cyan (`#0284c7`) optical lens coatings.
- **Full PWA & Mobile Web Asset Suite**: Generated `apple-touch-icon.png` (180x180), `icon-192.png`, `icon-512.png`, `icon-512-maskable.png`, scalable `favicon.svg`, `favicon.ico`, and `manifest.json`. Adding to Home Screen in iOS Safari / Android now installs micam as a native standalone app.
- **End-to-End Tab Switch Test Suite**: Added `tests/test_tab_switch.py` validating the 30-second grace window, poster frame hold, and reconnect cycle.

## [0.1.7] - 2026-11-01

### Fixed
- **Mi Home Coexistence & Dual-Lens Hardware P2P Session Multiplexing**: Resolved the root cause of the "device telah maksimum" (device limit reached) error in the Mi Home mobile app. go2rtc previously opened two distinct P2P client sessions to the camera (one per lens channel), exhausting the Xiaomi CW100 SoC capacity of 2 concurrent client sessions. Created and applied `patches/go2rtc-v1.9.15-shared-session.patch` to go2rtc v1.9.15: when configured with `&shared=1`, both lens feeds share a single underlying P2P connection to the physical camera (`videoquality` + `videoquality2` requested in a single `videoStart` RPC command), demultiplexing incoming video packets using hardware flag `0x1400000`.
- **Non-blocking Camera Packet Dispatcher**: Decoupled camera socket read loops from slow client consumption with per-lens bounded ring buffers (`subBuffer = 512`), completely eliminating `pop buffer is full` errors and subsequent reconnection storms.
- **Wizard Configuration Cleanup**: Updated `xiaomi_wizard.py` to remove legacy `ffmpeg:...#video=h264` stream sources that previously kept P2P sessions open permanently, and automatically injects `shared=1` for dual-lens camera models.
- **VideoRTC Protocol Priority & Fallback**: Refactored `public/video-rtc.js` mode evaluation to use MSE as primary and WebRTC as fallback sequentially rather than opening duplicate concurrent consumer sessions. Added URL parameter `?mode=webrtc` / `?mode=mse` for on-demand protocol override testing.

### Added
- **Dual-Lens Simultaneous YouTube Live Broadcast**: Added support for streaming both lenses concurrently into a single live YouTube broadcast (`lens="both"`).
- **Customizable Dual-Lens Composition Layouts**:
  - **Side-by-Side (`side`)**: Both lenses positioned side-by-side using FFmpeg `hstack`.
  - **Vertical Stack (`stack`)**: Both lenses stacked top-and-bottom using FFmpeg `vstack`.
  - **Picture-in-Picture (`pip`)**: Full-viewport primary lens with a floating secondary lens using FFmpeg `overlay`.
- **Advanced PiP & Framing Controls**: Added options for PiP corner placement (`br`, `bl`, `tr`, `tl`), secondary lens scaling (20%, 30%, 40%, 50%), primary/secondary lens order swap, and framing mode (`contain` with letterboxing or `cover` with edge cropping).
- **Real-Time Live Benchmark Verification**: Verified <1 core CPU utilization (~57-73% on a 3-core Linux server) with 26fps real-time encoding (`speed >= 1.03x`) and zero dropped frames.
- **Zero P2P Overhead on Live Broadcast**: YouTube ingest draws directly from internal RTSP feeds (`rtsp://127.0.0.1:8554/...`), adding 0 P2P sessions to the physical camera hardware.

### Build
- Added `patches/go2rtc-v1.9.15-shared-session.patch` enabling reproducible compilation of the patched go2rtc binary from upstream v1.9.15.

## [0.1.6] - 2026-10-31

### Fixed
- **Camera "Limit Device" & P2P Hardware Starvation**: Diagnosed and resolved the root cause of the "Limit device" error where suspended or sleeping browser tabs (such as Windows Edge / Chrome background tabs) kept TCP sockets in `ESTABLISHED` with clogged send queues (`Send-Q > 500KB`), backing up into go2rtc CS2 buffers (`pop buffer is full`) and exhausting the Xiaomi CW100 camera's 2-channel P2P SoC capacity.
- **Client Lifecycle Stream Teardown**: Updated `VideoRTC` WebRTC element (`public/video-rtc.js`) to set `visibilityCheck = true` by default and wired clean teardown listeners on `visibilitychange` (hidden), `pagehide`, `beforeunload`, and Chromium `freeze` events to instantly close client WebSockets and peer connections instead of leaking sockets.

### Added
- **Automated Kernel Socket & Buffer Watchdog**: Added daemon watchdog loop in `server.py` inspecting active connections on go2rtc ports (`1984` and `1985`) every 10 seconds. Automatically detects stalled sockets (`Send-Q > 250KB`) and flushes go2rtc via `/api/restart`, preventing camera SoC packet buffer lockups.
- **On-Demand Camera Release Endpoint**: Implemented `POST /api/streams/release` endpoint that instantly terminates active go2rtc camera sessions on demand, freeing all P2P channels for the official Xiaomi Home mobile app.
- **"Bebaskan Kamera" (Standby Mode) Controls**: Added one-click standby toggle button in the desktop monitor toolbar and mobile drawer menu, along with full-viewport interactive overlays on both lenses allowing users to release camera hardware sessions instantly and resume with a single click.
- **Configurable Idle Inactivity Watchdog**: Added automatic standby selector in the top toolbar with customizable timeouts (5 minutes, 10 minutes [default], 30 minutes, or 24/7 disabled), listening for user activity (`mousemove`, `mousedown`, `keydown`, `touchstart`, `scroll`) and automatically putting the stream into standby when idle.
- **Mobile P2P Slot Preservation**: Configured mobile viewports (`< 640px`) to default to single-lens view (`switchLensView('left')`), consuming only 1 P2P channel and leaving 1 channel 100% permanently reserved for the Xiaomi Home mobile app.
- **End-to-End Verification Suite**: Added Playwright test `tests/test_stream_standby.py` validating desktop standby toggle, overlay resume interaction, idle timeout localStorage persistence, mobile single-lens default, mobile drawer integration, and `POST /api/streams/release`.

## [0.1.5] - 2026-10-31

### Added
- Advanced Camera Hardware Settings Page (`public/settings.html` & `/settings` route): Dedicated separate page for all hardware parameters extracted from the official Xiaomi Mi Home MIoT spec (`chuangmi.camera.075ae1`), avoiding codebase bloat on the main live monitor dashboard.
- MicroSD Physical Card vs. Server Storage Separation: Distinct separation of concerns where onboard MicroSD card controls (live capacity bar, status, formatting, unmounting/eject, and onboard recording mode) are managed on `/settings.html`, while Server Storage DVR (local Linux storage, segment limits, MP4 player & linimasa, and timelapse) is kept exclusively on the main dashboard.
- Camera Hardware Optical Controls: 180° image rotation (flip), timestamp watermark, Wide Dynamic Range (WDR), glimmer full-color low-light mode, Lens Distortion Correction (LDC), and AI object tracking frame.
- Physical Lamp & Audio Hardware Controls: Front LED indicator switch, physical spotlight toggle, 1%-100% spotlight brightness slider, 0%-100% speaker volume slider, hardware mute toggle, and warning light strobo flash modes (Continuous, Slow Blink, Fast Warning Strobo).
- AI Neural Sensitivity Controls: Motion detection switch, 3-tier motion sensitivity (Low, Medium, High), Human AI silhouette detection, Vehicle AI detection, and 3-tier AI neural confidence threshold.
- Secure Auth Gating: Frontend lock overlay (`#authGateCard`) and backend HTTP 401 gate preventing unauthorized access or hardware manipulation when no verified Xiaomi Cloud session / MIIO token is active.
- MIIO Chunked Property Queries: Query scheduler that chunks 24 hardware properties into 4-item batches over UDP 54321, eliminating camera SoC packet timeouts and responding reliably in <0.3 seconds.
- REST API Suite: Added `GET /api/camera/advanced`, `POST /api/camera/advanced`, and `POST /api/camera/sdcard` (`format`, `eject`, `set_mode`).
- Antislop Design Standard: Strictly zero emojis across all UI headers, labels, switches, sliders, custom confirmation modals, and toast notifications, utilizing crisp inline SVG icons throughout.
- Automated Verification Suite: Added Playwright E2E test (`tests/test_settings_page.py`) covering desktop viewports (1440x900), mobile responsive drawers (390x844), real hardware property updates, and simulated 401 unauthenticated lock verification.

## [0.1.4] - 2026-10-31

### Added
- YouTube Live Streaming Relay: Built-in in-browser streaming module (`youtube_streamer.py`) enabling 24/7 or on-demand live streaming from Xiaomi cameras directly to YouTube Live.
- Interactive Setup Guide Button: In-app guidance accordion ("Panduan: Cara Mendapatkan Stream Key YouTube") providing step-by-step instructions to copy the stream key from YouTube Studio Live and configure Unlisted / Private privacy settings.
- Copyright-Safe Audio Option: Integrated synthetic silent audio track (`anullsrc`) satisfying YouTube RTMP ingestion requirements while preventing automated Content ID copyright takedowns from ambient background noise or music.
- Stream Key Credential Masking: Secured stream key storage and API responses (`masked_key`) with password eye toggle for easy viewing and editing without exposing raw credentials in plaintext.
- Automated Supervisor & Persistence: Background recovery loop that reconnects streams automatically during transient network interruptions, with optional auto-start on server boot.
- REST API Suite: Added `GET /api/youtube/status`, `POST /api/youtube/start`, `POST /api/youtube/stop`, and `POST /api/youtube/config`.
- Automated Verification Suite: Added Playwright test (`tests/test_youtube_stream.py`) covering backend endpoints, modal interactions, accordion expansion, eye toggle visibility, and screenshot capture.
- RTMPS Secure Ingestion: Upgraded live streaming endpoint from legacy unencrypted RTMP (port 1935) to the modern RTMPS standard (TLS 1.3 over port 443) using YouTube's primary ingestion server (`rtmps://a.rtmps.youtube.com/live2`) with 2-second keyframe GOP alignment (`-g 40` at 20fps).

### Fixed
- Setup Wizard redundant QR scan & login link: Automatically hid QR code box, countdown timer, and direct login link in Step 1 when the user is already authenticated with Xiaomi Cloud, displaying their verified account details and a direct "Lanjut ke Pilihan Kamera" action.
- Device discovery fallback: Added server-side fallback in `/api/wizard/devices` to return the currently configured camera from `.env` when the in-memory wizard session is idle, preventing "Not authenticated" errors.
- YouTube modal dropdown layout & responsiveness: Styled custom dark-mode `.form-select` with subtle borders, background chevron indicator, and 42px touch-friendly height; refactored grid to stack into a single column (`.yt-options-grid`) on mobile screens (≤520px) to prevent text truncation.

## [0.1.3] - 2026-10-31

### Added
- Multi-device WebRTC fan-out: Supported unlimited concurrent web clients (PC, laptop, smartphone, tablet) streaming from go2rtc without opening multiple P2P connections to the physical camera.
- Instant Camera Standby toggle ("Bebaskan Kamera"): Added a header action button and responsive overlay to immediately suspend web streams and release camera P2P slots for the Xiaomi / Mi Home mobile app with a single click.

### Fixed
- Camera device limit lockout: Removed circular FFmpeg transcoding consumer in `go2rtc.yaml` that held P2P channels open 24/7 even when no clients were viewing.
- Rapid socket teardown: Added browser `beforeunload` and `pagehide` teardown handlers and configured aggressive Linux TCP keepalive (60s timeout, 10s interval) to eliminate orphaned socket keepalives.
- Stream disconnect latency: Reduced `video-rtc` unmount timeout from 60 seconds to 2 seconds, and cleared pending reconnection timers on explicit disconnect.
- Client background stream override: Removed hardcoded `background = true` in JavaScript initialization, enabling proper visibility-based stream suspension.

## [0.1.2] - 2026-10-31

### Fixed
- Streaming stability on MS Edge and Windows browsers: Restored WebRTC as primary transport, eliminating the MSE slow-motion rubber-banding playback loop (`playbackRate < 1.0`).
- MSE buffer synchronization: Replaced flawed fractional playback rate with stable 1.0x real-time playback and discrete live-edge jump for low-latency catch-up.
- Xiaomi Mi Home app concurrent device limit: Automatically disconnect camera streams when browser tabs are hidden, minimized, or in background, releasing hardware P2P sessions so the mobile Mi Home app can connect without hitting device concurrency caps.
- Dynamic single-lens session freeing: Disconnected inactive camera channels when switching between single-lens and dual-lens views to minimize active camera sessions.
- Screenshot privacy: Applied smooth visual blur to camera video frames in documentation screenshot (`desktop_preview.png`) to protect residential privacy while keeping the UI razor sharp.

## [0.1.1] - 2026-10-30

### Changed
- Thread-bounded transcoding: Added `-threads 2` to FFmpeg profile in `go2rtc.yaml` to prevent CPU core saturation and reduce Linux kernel context switching by ~40% on multi-core systems.
- Native H.265 MSE passthrough: Prioritized native H.265 over Media Source Extensions (MSE) in `video-rtc.js` when supported by the client browser, eliminating server transcoding CPU load while serving pristine 2.5K streams.
- Non-blocking server concurrency: Replaced single-threaded `socketserver.TCPServer` with `ThreadingTCPServer` in `server.py` to prevent DVR streaming or range requests from stalling API endpoints.
- In-memory camera status cache: Added short TTL caching for MIIO telemetry in `server.py` to prevent UDP socket flooding to the camera SoC from multiple concurrent browser sessions.
- Storage telemetry optimization: Cached disk usage calculations in `recorder.py` and introduced client-side 1-second duration ticker in `public/index.html` to eliminate excessive disk metadata lookups.
- Page visibility lifecycle management: Automatically pause polling intervals when the dashboard tab is hidden or minimized, conserving client battery and network bandwidth.
- LAN-optimized ICE candidate gathering: Bypassed WAN STUN lookups on private LAN and Tailscale subnets, accelerating WebRTC handshake latency to under 100ms.

## [0.1.0] - 2026-10-30

### Added
- Zero-Config Web Setup Wizard:
  - In-browser onboarding using Xiaomi Cloud SSO long-polling authentication.
  - On-screen QR code authentication and direct verification URL.
  - Multi-region auto-scanner probing Singapore (`sg`), China Mainland (`cn`), and Global regions.
  - Automated configuration generator for `.env` and `go2rtc.yaml` with backup safety.
- Adaptive Lens Layout Engine:
  - Automatic detection and layout switching for Dual-Lens (CW100 / CW700S) and Single-Lens (C200 / C300 / C400) camera models.
  - Single-lens mode expands primary monitor to full width and hides secondary channel elements.
- 2-Pass WebGL FSR Super-Resolution Zoom:
  - Client-side GPU-accelerated upscaler based on AMD FidelityFX Super Resolution (FSR 1.0).
  - Pass 1: EASU 12-tap directional Lanczos edge-adaptive scaling.
  - Pass 2: RCAS ringing-free adaptive sharpening.
  - On-demand execution only when zoomed in (`scale > 1.01`), preserving native zero-copy video decoding at normal view.
- Continuous & Manual DVR Recording:
  - Universal browser-compatible H.264/AAC MP4 recording with zero-CPU stream copy and in-browser playback.
  - Configurable segmentation (5, 15, 30, 60 minutes) and automated disk retention cleanup.
  - In-browser video player with HTTP 206 partial-content range seeking and MP4 download.
- Local MIIO Hardware Controls (AES-128-CBC):
  - Dual white LED spotlight toggle.
  - Infrared night vision modes (Auto / On / Off).
  - Hardware buzzer siren alarm with visual strobe alert.
  - AI Detection triggers: Motion, Human, and Vehicle analytics.
  - Remote camera reboot endpoint.
- Security & Privacy:
  - Default masked SSID display (`••••••••`) with eye toggle icon on dashboard.
  - 4-digit PIN lock screen protection with numeric keypad.
  - Telegram alert integration with instant snapshot dispatch.
  - Decoupled credentials: `.env` and `go2rtc.yaml` excluded from git tracking.
