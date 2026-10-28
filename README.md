# Xiaomi Outdoor Camera CW100 Dual • Surveillance & DVR Dashboard

Sistem pemantauan, kontrol hardware, dan perekam video (DVR) mandiri (*100% self-contained & self-hosted*) untuk kamera pintar **Xiaomi Outdoor Camera CW100 Dual-Lens** (`chuangmi.camera.075ae1`).

Proyek ini telah dibuat **berdikari penuh**: seluruh logika backend, frontend, gateway streaming, dan engine DVR berada di dalam folder ini tanpa dependensi path eksternal.

---

## 🌟 Fitur Utama

- **Dual-Lens Live Streaming Simultan:**
  - Lensa 1: Wide Angle (Utama)
  - Lensa 2: PTZ Telephoto (Sekunder)
  - Protokol WebRTC, MSE, dan RTSP lokal berlatensi sangat rendah (~200ms).
  - Resolusi 2.5K / HD dengan kompresi H.265 (HEVC).
- **Perekam Video (DVR) & Manajemen Penyimpanan:**
  - **Rekam Manual Seketika:** Tombol rekam langsung di monitor kamera (dengan timer realtime) atau panel DVR.
  - **DVR Otomatis 24/7 Continuous:** Perekaman otomatis tanpa henti yang dipecah per segmen file MP4 (pilihan 5, 15, 30, atau 60 menit).
  - **Performa Ringan (*Stream Copy*):** Beban CPU server ~0% karena video langsung disalin (*codec copy*) tanpa rendering/transcoding ulang.
  - **Galeri Rekaman & Video Player:** Tonton video rekaman langsung di browser dengan fitur *scrub/seek* maju-mundur lancar (HTTP 206 Partial Content).
  - **Download & Delete:** Unduh file `.mp4` asli atau hapus dengan 1 klik.
  - **Auto-Cleanup & Retensi:** Pembersihan file rekaman otomatis berdasarkan umur (3/7/14/30 hari) atau jika sisa kapasitas disk di bawah ambang batas (5 GB).
- **Kontrol Perangkat Keras Langsung (MIIO RPC AES-128):**
  - 💡 Saklar Lampu Sorot LED Putih (*Dual White Spotlight*).
  - 🌙 Saklar Night Vision Inframerah (Auto / On / Off).
  - ⚡ Saklar Siaga / Aktif Sensor Lensa Kamera.
  - 🔄 Restart Kamera CCTV jarak jauh.
- **Telemetri Jaringan Realtime:**
  - Pemantau sinyal Wi-Fi RSSI (dBm), latensi RTT ping, SSID pemancar, dan status channel.
- **Otentikasi & Manajemen Sesi Satset:**
  - Modal akun Xiaomi langsung di web dashboard.
  - Verifikasi kode OTP Xiaomi jika diperlukan re-otentikasi di masa mendatang.
- **Antarmuka Modern (Pure OLED Black):**
  - Tema hitam pekat (*true black `#000000`*) bebas abu-abu, berdesain antislop surveillance.
  - 100% responsif di smartphone dan desktop dengan standar target sentuh minimal 44x44px.

---

## 📁 Struktur Direktori

```text
cctv_dashboard/
├── public/
│   └── index.html         # Frontend Dashboard (Pure Black, WebRTC, Controls, DVR UI)
├── server.py              # Backend REST API Server (Port 8088, Video Streaming HTTP 206)
├── recorder.py            # Engine Perekaman DVR FFmpeg, Retensi Disk & Auto-Cleanup
├── go2rtc.yaml            # Konfigurasi gateway streaming P2P / WebRTC
├── start.sh               # Skrip inisialisasi & peluncuran 1-klik (otomatis download go2rtc)
├── stop.sh                # Skrip penghentian layanan
├── requirements.txt       # Dependensi Python (pycryptodome)
├── .env.example           # Contoh variabel lingkungan konfigurasi kamera
└── README.md              # Dokumentasi lengkap proyek
```

---

## 🚀 Prasyarat Sistem

1. **Sistem Operasi:** Linux (Ubuntu, Debian, Raspberry Pi OS, Arch, dll.)
2. **Python:** Python 3.8+
3. **FFmpeg:** Diperlukan untuk perekaman DVR (`sudo apt install ffmpeg`)
4. **Jaringan:** Server berada di jaringan Wi-Fi/LAN yang sama dengan CCTV Xiaomi.

---

## 🛠️ Cara Instalasi & Menjalankan

### 1. Clone Repositori
```bash
git clone https://github.com/<username>/cctv_dashboard.git
cd cctv_dashboard
```

### 2. Instal Dependensi Python
```bash
pip3 install -r requirements.txt
```

### 3. Konfigurasi (Opsional)
Secara default, parameter kamera sudah siap pakai. Jika IP atau token kamera Anda berbeda, Anda dapat menyetelnya via environment variables atau membuat file `.env`:
```bash
cp .env.example .env
# Edit CCTV_CAMERA_IP, CCTV_TOKEN_HEX, atau CCTV_DID jika diperlukan
```

### 4. Jalankan Sistem (1-Klik)
```bash
chmod +x start.sh stop.sh
./start.sh
```
Skrip `start.sh` akan otomatis:
- Memeriksa dependencies
- Mengunduh binary `go2rtc` resmi jika belum ada
- Menjalankan gateway WebRTC di port `1984`
- Menjalankan Web Dashboard di port `8088`

### 5. Akses Dashboard
Buka browser favorit Anda (Desktop maupun HP):
```text
http://<IP_SERVER>:8088
```

Untuk menghentikan semua layanan:
```bash
./stop.sh
```

---

## 📡 Alamat Endpoint Streaming Lokal

Selain melalui Web Dashboard, Anda juga dapat mengintegrasikan stream CCTV ini ke **Home Assistant, Frigate NVR, Scrypted, atau VLC Media Player**:

- **Lensa 1 (Kiri):**
  - RTSP: `rtsp://<IP_SERVER>:8554/cctv_garasi_kiri`
  - WebRTC / MSE: `http://<IP_SERVER>:1984/stream.html?src=cctv_garasi_kiri`
- **Lensa 2 (Kanan):**
  - RTSP: `rtsp://<IP_SERVER>:8554/cctv_garasi_kanan`
  - WebRTC / MSE: `http://<IP_SERVER>:1984/stream.html?src=cctv_garasi_kanan`

---

## 🔒 Keamanan & Lisensi
Proyek ini bersifat open-source untuk penggunaan pribadi (*self-hosted*). Pastikan port kamera dan dashboard tidak diekspos ke publik tanpa proteksi firewall atau VPN (*Tailscale / WireGuard*).
