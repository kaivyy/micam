# Troubleshooting Guide

This guide covers common setup issues, network edge cases, and performance tuning for the Xiaomi CW100 surveillance system.

---

## 1. Credentials & Token Extraction

### Symptom: `server.py` cannot communicate with camera (`online: false` or socket timeout)
- **Root Cause:** Incorrect IP address, invalid token hex, or wrong Device ID (DID).
- **Solution:**
  1. Verify the camera is powered on and connected to your local WiFi.
  2. Ping the camera IP: `ping <CAMERA_IP>`.
  3. Extract fresh credentials using the [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor):
     ```bash
     bash <(curl -L -s https://raw.githubusercontent.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/master/token_extractor.sh)
     ```
  4. Select server region: `sg` (Singapore).
  5. Copy the extracted 32-character hexadecimal token and DID into `.env`:
     ```bash
     CCTV_CAMERA_IP=192.168.1.XX
     CCTV_TOKEN_HEX=your_32_char_hex_token
     CCTV_DID=your_device_did
     ```
  6. Restart the dashboard service:
     ```bash
     sudo systemctl restart cctv-dashboard
     ```

---

## 2. Streaming & WebRTC Gateway (`go2rtc`)

### Symptom: WebRTC stream displays loading spinner indefinitely
- **Check 1: Service Status**
  Verify `go2rtc` is actively running:
  ```bash
  pgrep -l go2rtc
  curl -s http://127.0.0.1:1984/api/streams
  ```
- **Check 2: PassToken Expiry**
  Xiaomi session tokens (`PassToken`) expire periodically. If the stream stops working after several weeks:
  1. Open the dashboard modal: **Manajemen Sesi & Akun Xiaomi**.
  2. Click **Sinkronkan Ulang Gateway Stream** or enter your credentials.
  3. Check `go2rtc.log` for session errors:
     ```bash
     tail -n 50 go2rtc.log
     ```
- **Check 3: UDP Firewall / Ports**
  The camera uses UDP port `54321` for local P2P negotiation. Ensure your host firewall (UFW / iptables) allows local UDP traffic:
  ```bash
  sudo ufw allow 54321/udp
  sudo ufw allow 1984/tcp
  sudo ufw allow 8554/tcp
  sudo ufw allow 8555/udp
  ```

---

## 3. Two-Way Audio / Microphone (Intercom)

### Symptom: Microphone button opens error modal or browser blocks permission
- **Root Cause:** Modern mobile and desktop browsers (Google Chrome, Apple Safari) block `navigator.mediaDevices.getUserMedia` when loaded over insecure HTTP connections (except `localhost`).
- **Solution:**
  - **Local Dev:** Connect using `http://localhost:8088` or `http://127.0.0.1:8088`.
  - **Remote / Mobile Access:** Put the dashboard behind a reverse proxy with an SSL/TLS certificate (such as Nginx Proxy Manager, Caddy, or Cloudflare Tunnel) to access via `https://`.
  - **Quick Alarm:** If mic access is unavailable, use the **Bunyikan Sirine Alarm** button which sends an instant hardware command directly over MIIO without requiring browser microphone permissions.

---

## 4. Mobile Browser Backgrounding & Tab Switching

### Symptom: Video reloads or freezes when switching between apps or browser tabs
- **Root Cause:** Mobile operating systems (iOS Safari and Android Chrome) aggressively freeze WebRTC sockets and suspend video elements in inactive background tabs to conserve battery.
- **Solution:**
  The dashboard includes automatic background recovery:
  1. The `<video-rtc background>` attribute keeps WebRTC peers resilient.
  2. A `visibilitychange` and `pageshow` listener automatically recovers frozen video elements upon re-entering the tab without requiring a manual page refresh.
  3. If video freeze persists due to network handoff (e.g. WiFi to 5G), tap the reload button in the lens header.

---

## 5. DVR & Storage Issues

### Symptom: Recordings are not saving or files are 0 bytes
- **Check 1: FFmpeg Installation**
  Verify FFmpeg is installed and accessible in the system PATH:
  ```bash
  ffmpeg -version
  ```
- **Check 2: Storage Directory Permissions**
  Ensure the user running `server.py` has write permissions to the recordings directory:
  ```bash
  mkdir -p recordings
  chmod 755 recordings
  ```
- **Check 3: Disk Safety Threshold**
  The DVR engine automatically halts recording and purges expired segments if free disk space falls below **5.0 GB** to prevent system lockups. Check remaining disk space:
  ```bash
  df -h
  ```
