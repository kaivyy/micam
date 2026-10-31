# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2026-10-31

### Added
- YouTube Live Streaming Relay: Built-in in-browser streaming module (`youtube_streamer.py`) enabling 24/7 or on-demand live streaming from Xiaomi cameras directly to YouTube Live.
- Interactive Setup Guide Button: In-app guidance accordion ("Panduan: Cara Mendapatkan Stream Key YouTube") providing step-by-step instructions to copy the stream key from YouTube Studio Live and configure Unlisted / Private privacy settings.
- Copyright-Safe Audio Option: Integrated synthetic silent audio track (`anullsrc`) satisfying YouTube RTMP ingestion requirements while preventing automated Content ID copyright takedowns from ambient background noise or music.
- Stream Key Credential Masking: Secured stream key storage and API responses (`masked_key`) with password eye toggle for easy viewing and editing without exposing raw credentials in plaintext.
- Automated Supervisor & Persistence: Background recovery loop that reconnects streams automatically during transient network interruptions, with optional auto-start on server boot.
- REST API Suite: Added `GET /api/youtube/status`, `POST /api/youtube/start`, `POST /api/youtube/stop`, and `POST /api/youtube/config`.
- Automated Verification Suite: Added Playwright test (`tests/test_youtube_stream.py`) covering backend endpoints, modal interactions, accordion expansion, eye toggle visibility, and screenshot capture.

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
