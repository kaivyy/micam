# REST API Documentation

The CCTV Dashboard Server (`server.py`) exposes a REST API on port `8088`. All requests and responses use standard JSON formatting unless streaming binary media.

---

## 1. System & Hardware Status

### `GET /api/status`
Returns live camera state queried directly via local MIIO protocol (UDP 54321).

**Response (200 OK):**
```json
{
  "online": true,
  "info": {
    "model": "chuangmi.camera.075ae1",
    "mac": "AA:BB:CC:DD:EE:FF",
    "fw_ver": "4.3.7_0320",
    "ap": {
      "ssid": "Home-Network",
      "bssid": "00:11:22:33:44:55",
      "rssi": -42
    }
  },
  "properties": [
    {"did": "1234567890", "siid": 2, "piid": 1, "code": 0, "value": true},
    {"did": "1234567890", "siid": 16, "piid": 1, "code": 0, "value": false},
    {"did": "1234567890", "siid": 2, "piid": 3, "code": 0, "value": 2},
    {"did": "1234567890", "siid": 9, "piid": 1, "code": 0, "value": 2},
    {"did": "1234567890", "siid": 9, "piid": 9, "code": 0, "value": 0},
    {"did": "1234567890", "siid": 5, "piid": 1, "code": 0, "value": true},
    {"did": "1234567890", "siid": 8, "piid": 6, "code": 0, "value": true},
    {"did": "1234567890", "siid": 8, "piid": 21, "code": 0, "value": false}
  ],
  "timestamp": 1730300000.123
}
```

### `GET /api/ping`
Tests low-level network round-trip time (RTT) directly to camera UDP port 54321.

**Response (200 OK):**
```json
{
  "alive": true,
  "rtt_ms": 1.42
}
```

### `GET /api/auth/status`
Returns Xiaomi Cloud authentication state and configured stream names.

**Response (200 OK):**
```json
{
  "authenticated": true,
  "user_id": "1234567890",
  "email": "user@example.com",
  "region": "sg",
  "did": "1234567890",
  "model": "chuangmi.camera.075ae1",
  "cctv_name": "Xiaomi CW100 Dual",
  "streams": {
    "kiri": "cctv_lensa_kiri",
    "kanan": "cctv_lensa_kanan"
  }
}
```

---

## 2. Hardware Controls

### `POST /api/control/light`
Toggles the dual LED spotlights.
- **Payload:** `{"state": true}` or `{"state": false}`
- **Response:** `{"success": true, "state": true}`

### `POST /api/control/power`
Toggles camera standby mode (both sensor lenses on/off).
- **Payload:** `{"state": true}` (active) or `{"state": false}` (sleep)
- **Response:** `{"success": true, "state": true}`

### `POST /api/control/nightshot`
Configures night vision / infrared behavior.
- **Payload:** `{"value": 0}` (Off), `{"value": 1}` (Always On), `{"value": 2}` (Auto)
- **Response:** `{"success": true, "value": 2}`

### `POST /api/control/siren`
Triggers the physical emergency siren buzzer on the camera hardware.
- **Payload:** `{}`
- **Response:** `{"success": true, "result": {...}}`

### `POST /api/control/ai`
Toggles individual AI analytics filters on camera firmware.
- **Payload:**
  - `{"type": "motion", "value": true}`
  - `{"type": "human", "value": true}`
  - `{"type": "car", "value": false}`
- **Response:** `{"success": true, "type": "human", "value": true}`

### `POST /api/control/ptz`
Controls physical pan-tilt-zoom motor (if supported by firmware).
- **Payload:** `{"action": "left" | "right" | "up" | "down"}`
- **Response:** `{"success": true, "result": {...}}`

### `POST /api/action/reboot`
Restarts the camera operating system remotely.
- **Payload:** `{}`
- **Response:** `{"success": true, "result": {...}}`

---

## 3. Snapshots & Telegram

### `GET /api/snapshot/<lens>`
Fetches an instant full-resolution JPEG snapshot from the video gateway.
- **Parameters:** `<lens>` can be `kiri`, `left`, `kanan`, or `right`.
- **Response:** `image/jpeg` binary data.

### `POST /api/telegram/send`
Captures a live snapshot and forwards it directly to a Telegram user or group.
- **Payload:**
  ```json
  {
    "bot_token": "123456789:ABCdefGhIJKlmNoPQR",
    "chat_id": "987654321",
    "lens": "left"
  }
  ```
- **Response:** `{"success": true, "telegram": {...}}`

---

## 4. DVR Recording & Playback

### `GET /api/record/status`
Returns active recording state and disk utilization.

**Response (200 OK):**
```json
{
  "active": true,
  "manual_recording": false,
  "config": {
    "enabled": true,
    "segment_minutes": 15,
    "retention_days": 7,
    "record_left": true,
    "record_right": true,
    "storage_dir": "/root/cctv_dashboard/recordings"
  },
  "current_files": {
    "left": "rec_left_20261030_160000.mp4",
    "right": "rec_right_20261030_160000.mp4"
  },
  "disk": {
    "total_gb": 120.5,
    "used_gb": 45.2,
    "free_gb": 75.3,
    "percent": 37.5
  }
}
```

### `POST /api/record/start`
Starts a manual recording session.
- **Payload:** `{"lens": "left" | "right" | "both"}`
- **Response:** `{"success": true, "result": {...}, "status": {...}}`

### `POST /api/record/stop`
Stops an ongoing manual recording session.
- **Payload:** `{"lens": "left" | "right" | "both"}`
- **Response:** `{"success": true, "result": {...}, "status": {...}}`

### `POST /api/record/settings`
Updates DVR operational parameters dynamically without restarting the server.
- **Payload:**
  ```json
  {
    "enabled": true,
    "segment_minutes": 30,
    "retention_days": 14,
    "record_left": true,
    "record_right": true
  }
  ```
- **Response:** `{"success": true, "status": {...}}`

### `GET /api/recordings`
Lists all stored MP4 recording files sorted chronologically.

**Response (200 OK):**
```json
{
  "recordings": [
    {
      "filename": "rec_left_20261030_154500.mp4",
      "lens": "left",
      "size_bytes": 178257920,
      "size_mb": 170.0,
      "mtime": 1730303100.0,
      "timestamp_str": "2026-10-30 16:00:00"
    }
  ],
  "status": {...}
}
```

### `GET /api/recordings/<filename>/stream`
Streams an MP4 file with full **HTTP 206 Partial Content** byte-range support. Supports browser scrubbing, forward seeking, and resumption.

### `GET /api/recordings/<filename>/download`
Initiates a standard file download attachment (`Content-Disposition: attachment`).

### `DELETE /api/recordings/<filename>`
Permanently removes a video recording from disk.
- **Response:** `{"success": true, "message": "Recording deleted successfully"}`

### `POST /api/record/timelapse`
Compiles recent recordings into a timelapse MP4 video.
- **Payload:** `{"lens": "left" | "right"}`
- **Response:** `{"success": true, "filename": "timelapse_left_1730303500.mp4"}`

---

## 5. Xiaomi Cloud Authentication

### `POST /api/auth/login`
Authenticates against Xiaomi Singapore cloud servers (`sg`) to retrieve or renew session credentials.
- **Payload:** `{"username": "...", "password": "..."}`
- **Response:** `{"status": 200, "response": "..."}`

### `POST /api/auth/verify_otp`
Submits 2FA one-time verification code when prompted by Xiaomi security checks.
- **Payload:** `{"code": "123456"}`
- **Response:** `{"success": true, "status": 200}`

### `GET /api/auth/reload_streams`
Triggers go2rtc to reload live streams from configuration.
- **Response:** `{"success": true, "streams": {...}}`

---

## 6. YouTube Live Streaming Relay

### `GET /api/youtube/status`
Returns current YouTube streaming status and configuration. Stream key is masked for privacy.

**Response (200 OK):**
```json
{
  "active": false,
  "stream_key_set": true,
  "masked_key": "abcd••••5678",
  "lens": "left",
  "quality": "native",
  "silent_audio": true,
  "auto_start": false,
  "started_at": null,
  "uptime_sec": 0,
  "last_error": null
}
```

### `POST /api/youtube/start`
Starts broadcasting the selected camera stream to YouTube Live using FFmpeg RTMP relay.
- **Payload:** Optional JSON configuration updates (see `POST /api/youtube/config`).
- **Response:** `{"success": true, "status": {...}}`

### `POST /api/youtube/stop`
Terminates active YouTube Live broadcasting process.
- **Response:** `{"success": true, "status": {...}}`

### `POST /api/youtube/config`
Persists YouTube streaming configuration parameters to disk (`youtube_config.json`).
- **Payload:**
```json
{
  "stream_key": "live_12345678_abcdefghijk",
  "lens": "left",
  "quality": "native",
  "silent_audio": true,
  "auto_start": false
}
```
- **Response:** `{"success": true, "status": {...}}`
