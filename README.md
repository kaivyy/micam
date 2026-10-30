<div align="center">

# Xiaomi Outdoor Camera CW100 Dual
### Surveillance, AI Control & NVR DVR Dashboard

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![WebRTC](https://img.shields.io/badge/Streaming-WebRTC%20%7C%20MSE%20%7C%20RTSP-0284c7?style=for-the-badge)](https://github.com/AlexxIT/go2rtc)
[![Codec](https://img.shields.io/badge/Codec-H.265%20%2F%20HEVC-10b981?style=for-the-badge)](https://ffmpeg.org)
[![UI](https://img.shields.io/badge/Theme-Pure%20OLED%20Black-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com)
[![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)](LICENSE)

*Sistem dashboard pengawasan, kontrol hardware pintar lokal, AI analytics, dan perekam video (DVR) mandiri (100% self-hosted & self-contained) untuk kamera pintar **Xiaomi Outdoor Camera CW100 Dual-Lens** (`chuangmi.camera.075ae1`).*

---

[Fitur Utama](#fitur-utama) • [Arsitektur](docs/ARCHITECTURE.md) • [Instalasi Cepat](#instalasi-cepat) • [REST API](docs/API.md) • [Integrasi NVR](docs/NVR_INTEGRATION.md) • [Troubleshooting](docs/TROUBLESHOOTING.md)

</div>

---

## Fitur Utama

- **Web Setup Wizard & Zero-Config Onboarding (Satset):**
  - **Setup 1-Klik di Browser**: Pengguna baru cukup membuka dashboard di browser. Jika belum ada kamera, wizard onboarding otomatis muncul.
  - **Login QR & Link SSO Mi Home**: Cukup scan QR code dari aplikasi Mi Home atau klik link verifikasi browser tanpa repot memasukkan token/DID manual di terminal.
  - **Auto-Scan Multi-Region**: Otomatis mendeteksi kamera di server Singapore (`sg`), China (`cn`), dan Global.
  - **Layout Adaptif Otomatis**: Mendukung kamera **Dual-Lens** (CW100 / CW700S) maupun **Single-Lens** (C200 / C300 / C400) secara otomatis tanpa layar kedua kosong.
- **2-Pass WebGL FSR Super-Resolution Zoom (EASU + RCAS):**
  - Rekonstruksi gambar zoom adaptif berbasis algoritma **AMD FidelityFX Super Resolution 1.0** di sisi client browser (WebGL).
  - Pass 1 (EASU 12-tap directional Lanczos) + Pass 2 (RCAS ringing-free sharpening) memberikan detail plat nomor, wajah, dan teks jauh lebih tajam dibanding interpolasi browser standar.
- **Dual-Lens Live Streaming Simultan (~200ms Latency):**
  - **Lensa 1:** Sensor Utama *Wide Angle* (2.5K / HD)
  - **Lensa 2:** Sensor Sekunder *Telephoto Long-Range* (2.5K / HD)
  - Streaming menggunakan teknologi **WebRTC & MSE** via gateway lokal, menghasilkan latensi sangat minim tanpa buffering cloud.
- **Digital Zoom & Pan Interaktif:**
  - Zoom independen 0–100% per lensa dengan preset cepat (0%, 25%, 50%, 100%).
  - Dukungan drag / pan intuitif di desktop maupun layar sentuh smartphone.
- **Audio Fokus & Dua Arah (Intercom):**
  - Mikrofon fisik terpadu dengan perlindungan **Anti-Gema Otomatis** (mendengarkan satu lensa me-mute lensa lainnya).
  - Bicara dua arah (*backchannel*) langsung dari browser ke speaker CCTV.
- **Emergency Siren / Alarm Suara Darurat:**
  - Memicu sirene buzzer hardware bawaan kamera seketika untuk peringatan bahaya di lokasi.
  - Dilengkapi animasi strobo visual pada dashboard saat aktif.
- **AI Smart Detection Analytics & Toggle Switch:**
  - Kontrol saklar deteksi pintar langsung ke kamera:
    - **General Motion Detection** (Deteksi Gerakan Umum)
    - **AI Human Detection** (Deteksi AI Bentuk Tubuh Manusia)
    - **AI Vehicle Detection** (Deteksi AI Kendaraan Mobil/Motor)
- **Telegram Alert Bot & Live Snapshot:**
  - Integrasi bot Telegram langsung dari dashboard: kirim notifikasi dan foto snapshot JPEG resolusi tinggi seketika ke ponsel pengguna.
- **24-Hour NVR Timeline Scrubber:**
  - Bilah linimasa 24 jam interaktif visual untuk meninjau rekaman sepanjang hari.
  - Fitur *click-to-seek* untuk langsung memutar rekaman pada jam tertentu.
- **Perekam Video (DVR) Cerdas & Zero-CPU Overhead:**
  - **Stream Copy (`-c copy`):** Video dan audio disalin langsung ke disk tanpa proses rendering ulang (*transcoding*), menjaga penggunaan CPU server mendekati **~0%**.
  - **DVR Otomatis 24/7 (Continuous):** Otomatis merekam dan memecah file video per segmen waktu (**5, 15, 30, atau 60 menit** per file `.mp4`).
  - **Rekam Manual Seketika:** Tombol rekam cepat di atas live feed dengan timer berkedip realtime.
  - **Auto-Cleanup & Manajemen Retensi:** Otomatis menghapus file rekaman terlama berdasarkan masa simpan (**3, 7, 14, 30 hari**) atau saat kapasitas harddisk menyentuh batas aman (< 5 GB).
- **In-Browser Video Player & File Manager:**
  - Putar rekaman langsung di browser dengan dukungan **HTTP 206 Partial Content Range** (bisa digeser maju/mundur dengan instan).
  - Unduh file `.mp4` asli atau hapus dengan satu klik.
- **PIN Security Guard / Lock Screen:**
  - Sistem penguncian dashboard 4 digit PIN dengan dialog keypad numerik untuk mencegah akses kontrol yang tidak diinginkan.
- **Kontrol Hardware Lokal Terenkripsi (MIIO RPC AES-128 CBC):**
  - **Lampu Sorot LED:** Saklar on/off lampu penerangan ganda (*dual white spotlight*).
  - **Night Vision (Infrared):** Mode Malam IR otomatis / nyala / mati.
  - **Sensor Lensa:** Saklar mode siaga (*sleep*) / aktif kedua sensor kamera.
  - **Remote Reboot:** Mulai ulang perangkat CCTV langsung dari browser.
- **Desain Modern Pure OLED Black (`#000000`) & Bespoke SVG Icons:**
  - Tampilan tema hitam pekat tanpa kabur abu-abu, sangat tajam dan hemat daya pada layar OLED/AMOLED.
  - Menggunakan icon vektor SVG inline yang bersih dan profesional tanpa emoji.
  - Desain responsif (*mobile-friendly*) dengan target sentuh ibu jari minimal **44x44px** sesuai kaidah *antislop UI*.

---

## Dokumentasi Proyek

Panduan teknis mendalam tersedia di direktori [`docs/`](docs/):

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Arsitektur sistem, diagram alur, dan protokol jaringan.
- [docs/API.md](docs/API.md) — Spesifikasi lengkap endpoint REST API backend.
- [docs/NVR_INTEGRATION.md](docs/NVR_INTEGRATION.md) — Panduan integrasi Home Assistant, Frigate, Scrypted, dan VLC.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Solusi kendala token, P2P handshake, WebRTC, dan audio.

---

## Struktur Direktori

```text
cctv_dashboard/
├── docs/
│   ├── ARCHITECTURE.md    # Detail arsitektur & diagram protokol
│   ├── API.md             # Dokumentasi REST API server.py
│   ├── NVR_INTEGRATION.md # Panduan integrasi Frigate & Home Assistant
│   └── TROUBLESHOOTING.md # Solusi masalah umum & tuning performa
├── public/
│   ├── index.html         # Antarmuka Dashboard (OLED Black, WebRTC, Controls, DVR UI)
│   └── video-rtc.js       # WebRTC custom element gateway streaming
├── server.py              # Server REST API & Layanan Video Stream HTTP 206 (Port 8088)
├── recorder.py            # Engine Perekam DVR FFmpeg, Retensi Disk & Auto-Cleanup
├── start.sh               # Skrip inisialisasi & peluncuran 1-klik (auto-download go2rtc)
├── stop.sh                # Skrip penghentian layanan
├── requirements.txt       # Dependensi Python (pycryptodome)
├── .env.example           # Template variabel lingkungan (IP, Token, DID)
├── go2rtc.example.yaml    # Template konfigurasi gateway streaming P2P
├── LICENSE                # Lisensi MIT
└── README.md              # Dokumentasi pengantar proyek
```

---

## Instalasi Cepat

### 1. Prasyarat Sistem
- **Sistem Operasi:** Linux (Ubuntu, Debian, Raspberry Pi OS, Armbian, dll.)
- **Python:** Versi 3.8 atau lebih baru
- **FFmpeg:** Diperlukan untuk perekaman DVR:
  ```bash
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```

### 2. Clone Repositori
```bash
git clone https://github.com/<username>/cctv_dashboard.git
cd cctv_dashboard
```

### 3. Instal Dependensi Python
```bash
pip3 install -r requirements.txt
```

### 4. Jalankan Sistem (1-Klik)
```bash
chmod +x start.sh stop.sh
./start.sh
```
> [!NOTE]
> Skrip `start.sh` akan secara otomatis mendeteksi arsitektur prosesor (`x86_64`, `arm64`, `armv7l`) dan mengunduh binary resmi `go2rtc` jika belum tersedia di sistem.

### 5. Hubungkan CCTV via Web Setup Wizard (Satset)
Buka browser dan akses:
```text
http://<IP_SERVER_ANDA>:8088
```
1. Dashboard otomatis menampilkan dialog **Setup Wizard**.
2. Scan **QR Code** menggunakan aplikasi **Mi Home** (atau klik *Buka Link Verifikasi*).
3. Pilih kamera CCTV dari daftar yang terdeteksi di akun Anda.
4. Klik **Pasang & Aktifkan Kamera Ini** &mdash; sistem otomatis men-generate file konfigurasi dan live stream langsung tayang!

Untuk menghentikan layanan:
```bash
./stop.sh
```

---

## Integrasi NVR / Pihak Ketiga

Stream video RTSP lokal dapat langsung dihubungkan ke software NVR seperti **Frigate, Home Assistant, Scrypted, Zoneminder, Shinobi, atau VLC Media Player**:

| Lensa Kamera | Endpoint RTSP (Lokal) | Endpoint WebRTC / Browser |
| :--- | :--- | :--- |
| **Lensa 1: Wide Angle (Kiri)** | `rtsp://<IP_SERVER>:8554/cctv_lensa_kiri` | `http://<IP_SERVER>:1984/stream.html?src=cctv_lensa_kiri` |
| **Lensa 2: Telephoto (Kanan)** | `rtsp://<IP_SERVER>:8554/cctv_lensa_kanan` | `http://<IP_SERVER>:1984/stream.html?src=cctv_lensa_kanan` |

*Panduan konfigurasi lengkap Frigate dan Home Assistant tersedia di [docs/NVR_INTEGRATION.md](docs/NVR_INTEGRATION.md).*

---

## Estimasi Kebutuhan Harddisk (DVR 24/7)

Perekaman resolusi penuh 2.5K / HD dengan kompresi **H.265 (HEVC)** rata-rata memerlukan:
- **1 Lensa:** ~1.5 Mbps (±16 GB per 24 jam)
- **Kedua Lensa (Kiri + Kanan):** **±30 s/d 35 GB per 24 jam**
- **Kapasitas 85 GB:** Menampung ~2.5 hingga 3 hari rekaman nonstop.
- **Kapasitas 500 GB:** Menampung ~15 hingga 16 hari rekaman nonstop.
- **Kapasitas 1 TB:** Menampung ~1 bulan penuh (30 hari) rekaman nonstop.

---

## Kredit & Referensi Proyek

Proyek ini dibangun menggunakan fondasi dan terinspirasi dari proyek-proyek open-source hebat berikut:

- [go2rtc](https://github.com/AlexxIT/go2rtc) — Gateway streaming WebRTC, MSE, dan relay protokol P2P kamera Xiaomi (MISS / TUTK CS2).
- [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor) — Ekstraktor token lokal, Device ID, dan otentikasi akun Xiaomi cloud.
- [python-miio](https://github.com/rytilahti/python-miio) — Referensi protokol komunikasi UDP 54321 dan enkripsi AES-128-CBC MIIO.
- [FFmpeg](https://ffmpeg.org) — Framework multimedia untuk engine perekaman DVR *stream-copy* dan pemecah segmen video MP4.

---

## Lisensi

Didistribusikan di bawah lisensi [MIT License](LICENSE).
