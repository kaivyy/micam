# System Architecture

This document describes the high-level architecture, network protocols, and data flow of the Xiaomi Outdoor Camera CW100 Dual surveillance and NVR system.

## Overview

The system is designed as a lightweight, self-hosted, and low-latency surveillance gateway for the Xiaomi Outdoor Camera CW100 Dual-Lens (`chuangmi.camera.075ae1`). It bridges proprietary camera protocols (MIIO and TUTK/MISS P2P) into open standards: WebRTC for live viewing, RTSP for NVR ingestion, and MP4 stream copy for local DVR storage.

```mermaid
flowchart TD
    subgraph Camera ["Xiaomi CW100 Hardware"]
        CAM_L1["Primary Lens (Wide Angle)"]
        CAM_L2["Secondary Lens (Telephoto)"]
        CAM_MIIO["MIIO Daemon (UDP 54321 / AES-128-CBC)"]
        CAM_SPK["Physical Speaker (Opus Audio Sink)"]
    end

    subgraph Host ["Host Server / Gateway"]
        subgraph Stream_Gateway ["go2rtc (Port 1984 / 8554)"]
            P2P["Xiaomi P2P Driver (PassToken V1)"]
            WRTC_SRV["WebRTC / WebSocket Engine (:1984)"]
            RTSP_SRV["RTSP Server (:8554)"]
        end

        subgraph Backend ["Python Application Server (:8088)"]
            SRV["REST API Handler (server.py)"]
            MIIO_CLIENT["Encrypted MIIO Client"]
            DVR["DVR Recording Engine (recorder.py)"]
        end

        STORAGE[("Local Storage / Disk<br/>(MP4 Segments)")]
    end

    subgraph Clients ["Client Layer"]
        BROWSER["Web Dashboard (video-rtc Web Component)"]
        NVR["Third-Party NVR (Frigate / Home Assistant / Scrypted)"]
    end

    CAM_L1 -->|MISS P2P Video| P2P
    CAM_L2 -->|MISS P2P Video| P2P
    MIIO_CLIENT <-->|UDP 54321 RPC| CAM_MIIO

    P2P --> WRTC_SRV
    P2P --> RTSP_SRV

    WRTC_SRV <-->|WebRTC (H.265 / Opus)| BROWSER
    BROWSER -->|Two-Way Audio Backchannel| WRTC_SRV
    WRTC_SRV -->|Audio Uplink| CAM_SPK

    RTSP_SRV -->|RTSP Stream| NVR
    RTSP_SRV -->|RTSP Stream Copy (-c copy)| DVR

    DVR -->|MP4 Segment Chunks| STORAGE
    STORAGE -->|HTTP 206 Partial Content| SRV
    SRV <-->|REST API / Controls| BROWSER
```

---

## Core Components

### 1. Media Streaming Gateway (`go2rtc`)
- **Role:** Handles direct peer-to-peer connection with the camera firmware over the local network using Xiaomi cloud credentials (PassToken).
- **Inbound Protocol:** Xiaomi MISS / TUTK CS2 P2P tunnel directly to camera IP on port 54321/UDP.
- **Outbound Streams:**
  - **WebRTC (`/api/ws` on port 1984):** Ultra low-latency (~200ms) video delivery to browsers without re-encoding.
  - **RTSP (`rtsp://host:8554/<stream_name>`):** Standard RTSP stream for local DVR recorder, Frigate, and Home Assistant.
  - **Two-Way Audio (Intercom):** Captures browser microphone input and routes Opus/G.711 stream back into the camera speaker via WebRTC backchannel.

### 2. Backend Server (`server.py`)
- **Role:** Central REST API server and static web host running on port 8088. Built entirely with Python's standard library (`http.server`, `socket`, `hashlib`, `urllib`) plus `pycryptodome` for MIIO encryption.
- **Key Responsibilities:**
  - Manages hardware properties (LED spotlights, night vision modes, siren, motion/human/car AI toggles).
  - Encrypts and decrypts Xiaomi MIIO packets using AES-128-CBC with device tokens.
  - Serves recorded MP4 videos with HTTP 206 Partial Content support for fast browser seeking.
  - Manages DVR manual recording, status inspection, and background tasks.

### 3. DVR & Storage Engine (`recorder.py`)
- **Role:** Continuous and manual 24/7 video recorder.
- **Architecture:**
  - Spawns persistent background worker threads that monitor `ffmpeg` recording jobs.
  - Uses `-c copy` (stream copy) directly from the local RTSP endpoint. No transcoding or GPU acceleration required; CPU utilization remains negligible (~0-1%).
  - Automatically splits recording files into configurable time chunks (default 15 minutes).
  - Enforces automatic retention policy based on retention days and disk safety thresholds (stops or purges oldest files when available disk space is under 5 GB).

### 4. Frontend Web Dashboard (`public/index.html`)
- **Role:** Single-page dashboard designed with an OLED Pure Black interface (`#000000`).
- **Features:**
  - Dual simultaneous WebRTC monitors powered by `video-rtc.js`.
  - Independent digital zoom & pan controls per lens (0–100%).
  - Exclusive audio focus with anti-echo protection (listening to one lens automatically mutes the other).
  - 24-hour visual timeline scrubber with fast seeking.
  - Responsive mobile layout with touch targets conforming to accessibility guidelines (>=44px).

---

## Network Ports & Protocols

| Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- |
| **8088** | TCP (HTTP) | `server.py` | Dashboard UI, REST API, DVR HTTP 206 video playback |
| **1984** | TCP (HTTP/WS) | `go2rtc` | WebRTC signaling, MSE stream, HTTP snapshot API |
| **1985** | TCP (HTTPS/WSS) | `go2rtc` | Secure WebRTC signaling (if SSL configured) |
| **8554** | TCP (RTSP) | `go2rtc` | RTSP server for DVR engine and external NVRs |
| **8555** | TCP/UDP | `go2rtc` | WebRTC ICE candidate gathering and peer exchange |
| **54321** | UDP | Camera MIIO | Xiaomi encrypted local control RPC & P2P handshake |
