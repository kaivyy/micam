# NVR & Third-Party Integration Guide

The Xiaomi CW100 gateway re-broadcasts both camera lenses as high-definition RTSP streams on port `8554`. This allows easy integration with Home Assistant, Frigate, Scrypted, Agent DVR, and standard media players.

---

## Stream Endpoints Reference

Replace `<HOST_IP>` with the local IP address of your host machine running this gateway:

| Stream | Description | RTSP URI | WebRTC Browser URI |
| :--- | :--- | :--- | :--- |
| **Lensa 1** | Primary Wide Angle Sensor | `rtsp://<HOST_IP>:8554/cctv_lensa_kiri` | `http://<HOST_IP>:1984/stream.html?src=cctv_lensa_kiri` |
| **Lensa 2** | Secondary Telephoto Sensor | `rtsp://<HOST_IP>:8554/cctv_lensa_kanan` | `http://<HOST_IP>:1984/stream.html?src=cctv_lensa_kanan` |

---

## 1. Frigate NVR

Frigate can ingest both lenses directly via RTSP for 24/7 recording and hardware-accelerated object detection.

Add the following to your `config.yml`:

```yaml
cameras:
  cw100_wide:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/cctv_lensa_kiri
          roles:
            - record
            - detect
    detect:
      width: 2560
      height: 1440
      fps: 15
    record:
      enabled: true
      retain:
        days: 7
        mode: all

  cw100_tele:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/cctv_lensa_kanan
          roles:
            - record
            - detect
    detect:
      width: 2560
      height: 1440
      fps: 15
    record:
      enabled: true
      retain:
        days: 7
        mode: all
```

---

## 2. Home Assistant

### Option A: Generic Camera Integration (UI)
1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Generic Camera**.
3. Configure each lens:
   - **Stream Source:** `rtsp://<HOST_IP>:8554/cctv_lensa_kiri`
   - **RTSP transport protocol:** `tcp`
   - **Authentication:** None
4. Repeat for `cctv_lensa_kanan`.

### Option B: WebRTC Camera Card (Ultra Low-Latency)
If using the custom [WebRTC Camera](https://github.com/AlexxIT/WebRTC) component:

```yaml
type: custom:webrtc-camera
url: cctv_lensa_kiri
title: CW100 Lensa Wide
muted: true
ui: true
```

---

## 3. Scrypted (Apple HomeKit Secure Video)

To expose both lenses to Apple Home app with HKSV recording:
1. In Scrypted management console, install the **RTSP Camera Plugin**.
2. Add a new device named `CW100 Wide Angle`:
   - Set Stream URL to `rtsp://<HOST_IP>:8554/cctv_lensa_kiri`.
3. Add a second device named `CW100 Telephoto`:
   - Set Stream URL to `rtsp://<HOST_IP>:8554/cctv_lensa_kanan`.
4. Enable the **HomeKit** plugin in Scrypted and pair with your Apple Home Hub.

---

## 4. VLC Media Player

1. Open VLC Media Player.
2. Press `Ctrl + N` (or **Media** > **Open Network Stream**).
3. Enter `rtsp://<HOST_IP>:8554/cctv_lensa_kiri`.
4. Click **Play**.
