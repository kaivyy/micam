# Xiaomi CW100 Dual CCTV Surveillance System

Sistem pemantauan dan kontrol CCTV mandiri (*self-hosted surveillance dashboard*) untuk kamera pintar **Xiaomi Outdoor Camera CW100 Dual** (`chuangmi.camera.075ae1`).

## Fitur Utama
- **Dual Camera Live Stream:** Streaming langsung dua lensa (Lensa 1 Wide Angle & Lensa 2 PTZ Tele) secara simultan melalui WebRTC & MSE (~200ms latency).
- **Kontrol Perangkat Keras Langsung:**
  - 💡 Saklar Lampu Sorot LED (Dual Spotlight) via RPC terenkripsi AES-128.
  - 🌙 Pengaturan Night Vision (Infrared Auto / On / Off).
  - ⚡ Saklar Siaga / Aktif Sensor Lensa Kamera.
  - 🔄 Restart Kamera jarak jauh.
- **Telemetri Jaringan & Wi-Fi:** Meteran sinyal Wi-Fi dBm, latensi RTT ping realtime, SSID, dan versi firmware.
- **Otentikasi & Manajemen Sesi Terintegrasi (Satset):**
  - Modal otentikasi akun Xiaomi langsung di web dashboard.
  - Form verifikasi OTP / Captcha tanpa perlu akses terminal atau perintah curl manual.
  - 1-Click gateway synchronization.

## Struktur Direktori
- `server.py`: REST API & Web Server (port 8088).
- `public/index.html`: UI Dashboard modern, responsif, antislop surveillance theme.
- `go2rtc.yaml`: Konfigurasi streaming gateway P2P / WebRTC (port 1984).
- `start.sh`: Skrip peluncuran otomatis kedua daemon service.

## Cara Menjalankan
```bash
./start.sh
```
Akses dashboard di browser: `http://<IP_SERVER>:8088`
