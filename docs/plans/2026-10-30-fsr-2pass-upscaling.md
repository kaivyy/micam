# FSR 2-Pass WebGL Upscaling (EASU + RCAS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengimplementasikan Opsi 2 (2-Pass Super-Resolution WebGL Shader: AMD EASU + RCAS) pada CCTV Dashboard agar pembesaran zoom live stream dan snapshot terlihat sangat tajam dan bebas blur langsung di GPU client (HP/Laptop), tanpa membebani CPU/RAM server headless dan tanpa merusak fungsionalitas yang ada.

**Architecture:** Video stream WebRTC dari `<video-rtc>` dihubungkan ke canvas overlay WebGL2. Pass 1 (EASU - Edge-Adaptive Spatial Upsampling) melakukan rekonstruksi arah gradien piksel dari sensor 2.5K ke FBO (Framebuffer Object). Pass 2 (RCAS - Robust Contrast-Adaptive Sharpening) menajamkan detail mikro bebas dering (ringing-free) ke canvas layar. Jika WebGL dinonaktifkan atau terjadi error, sistem secara otomatis dan mulus (zero-breakage fallback) kembali ke rendering standar SVG.

**Tech Stack:** JavaScript (ES6+), WebGL2 / WebGL1, GLSL (AMD FidelityFX FSR 1.0.2 ported), HTML5 `<canvas>`, CSS3.

## Global Constraints
- Tidak merusak fungsionalitas yang sudah ada: WebRTC live, PTZ, DVR recording, dua lensa split, audio intercom, tab switching.
- Server CPU & RAM harus tetap mendekati 0% (~0.1% CPU, ~30 MB RAM) karena pemrosesan berjalan 100% di browser client.
- Zero-breakage fallback: Bila WebGL tidak didukung perangkat client atau dinonaktifkan pengguna, video tetap tampil normal seperti sebelumnya.
- Kode bersih tanpa slop (antislop guidelines), dokumentasi terintegrasi, dan variabel state persisten via `localStorage`.

---

### Task 1: Standalone WebGL FSR 2-Pass Upscaler Module (`public/fsr-upscaler.js`)

**Files:**
- Create: `public/fsr-upscaler.js`
- Test: `tests/test_fsr_upscaler.js`

**Interfaces:**
- Produces: Class `FsrUpscaler`
  - `constructor(videoEl, canvasEl, options)`
  - `init(): boolean`
  - `setCrop(scale, x, y, containerWidth, containerHeight)`
  - `setSharpness(sharpnessVal: number)`
  - `start(): void`
  - `stop(): void`
  - `renderFrame(): void`
  - `captureSnapshot(type: string, quality: number): Promise<Blob>`
  - `destroy(): void`

- [ ] **Step 1: Tulis unit test untuk FsrUpscaler (validasi shader & context initialization via Playwright/Node)**
- [ ] **Step 2: Implementasikan vertex shader dan 2 fragment shader (Pass 1 EASU, Pass 2 RCAS) di `public/fsr-upscaler.js`**
- [ ] **Step 3: Implementasikan FBO (Framebuffer Object) ping-pong pipeline dan uniform binding**
- [ ] **Step 4: Implementasikan `requestVideoFrameCallback` dengan fallback `requestAnimationFrame` serta lifecycle control**
- [ ] **Step 5: Verifikasi modul dapat meng-compile shader dan merender frame tanpa error**

---

### Task 2: Integrasi UI Control & Overlay Canvas di `public/index.html`

**Files:**
- Modify: `public/index.html`

**Interfaces:**
- Consumes: `FsrUpscaler` dari `public/fsr-upscaler.js`
- Produces:
  - `<canvas class="fsr-overlay-canvas" id="fsrCanvas_camLeft">`
  - `<canvas class="fsr-overlay-canvas" id="fsrCanvas_camRight">`
  - UI switch mode di popup zoom: "Standar (SVG)" vs "Ultra HD (2-Pass FSR)"
  - Sinkronisasi `updateZoomTransform` ke `fsrUpscaler.setCrop`

- [ ] **Step 1: Tambahkan elemen canvas overlay di dalam `containerCamLeft` dan `containerCamRight` dengan style overlay non-blocking (`pointer-events: none`)**
- [ ] **Step 2: Tambahkan kontrol pilihan mode "Standar (SVG)" / "Ultra HD (2-Pass FSR)" dan slider ketajaman di dalam Popup Zoom masing-masing lensa**
- [ ] **Step 3: Hubungkan instance `FsrUpscaler` dengan video feed `camLeft` dan `camRight` saat stream aktif**
- [ ] **Step 4: Sinkronkan transformasi pan & zoom (`state.scale`, `state.x`, `state.y`) ke input crop shader FSR**
- [ ] **Step 5: Implementasikan safe fallback: saat mode Standar dipilih atau WebGL gagal, canvas di-hide dan video SVG aktif kembali**
- [ ] **Step 6: Tangani event tab visibility (`visibilitychange`) agar loop render otomatis pause saat tab tidak aktif (hemat daya 100%)**

---

### Task 3: Peningkatan Resolusi Snapshot dengan Canvas FSR

**Files:**
- Modify: `public/index.html`

**Interfaces:**
- Consumes: `fsrUpscaler.captureSnapshot()`
- Produces: Snapshot instan kualitas ultra-jernih langsung dari canvas FSR saat 2-Pass aktif

- [ ] **Step 1: Perbarui fungsi `takeSnapshot()` di `index.html` untuk memeriksa apakah FSR aktif dan sedang menampilkan frame yang tajam**
- [ ] **Step 2: Jika FSR aktif, unduh frame langsung dari canvas 2-pass super-resolution; jika tidak, fallback ke API snapshot backend CAS**

---

### Task 4: Verifikasi Komprehensif & Uji Performa

**Files:**
- Test: Playwright automation script `tests/verify_fsr_dashboard.py`

- [ ] **Step 1: Jalankan browser headless via Playwright untuk memverifikasi dashboard:**
  - Stream WebRTC kedua lensa aktif dan sinkron
  - Pengalihan mode Standar <-> FSR 2-Pass berjalan instan tanpa glitch
  - Zoom 25%, 50%, 100% pada mode FSR menampilkan gambar yang tajam dan tidak freeze
  - Snapshot berfungsi pada kedua lensa
- [ ] **Step 2: Ukur penggunaan CPU dan memori server selama zoom FSR aktif (pastikan tetap ~0.1% CPU)**
- [ ] **Step 3: Tangkap screenshot hasil zoom FSR sebagai bukti verifikasi**
- [ ] **Step 4: Jalankan `graphify update .` untuk memperbarui knowledge graph repositori**
