# Web Setup Wizard & Zero-Config Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-terminal Web Setup Wizard for the Xiaomi CCTV Dashboard that allows any user to scan a QR code from the Mi Home app (or open a direct link), automatically discovers all cameras across regions (`sg`, `cn`, `de`, `us`), auto-detects Single vs. Dual Lens, and generates `.env` and `go2rtc.yaml` so the live stream starts immediately without manual configuration.

**Architecture:** A lightweight, isolated Python micro-module `xiaomi_wizard.py` manages Xiaomi Cloud long-polling authentication, device discovery, and configuration persistence. `server.py` exposes REST endpoints (`/api/wizard/*`). The frontend in `public/index.html` hosts a high-contrast dark-mode multi-step setup modal that auto-opens when unconfigured and adapts the player UI dynamically for single-lens vs. dual-lens cameras.

**Tech Stack:** Python 3, `pycryptodome` (ARC4 & AES), Vanilla ES6+ JavaScript, WebGL (existing FSR), HTML5/CSS3 (Antislop Dark), pytest / Playwright.

## Global Constraints
- Preserve existing streaming, WebGL FSR upscaling, DVR recording, and PTZ controls.
- Maintain Antislop Dark theme guidelines (`#000000`, surface `#0d0f12`, border `#222222`, accent `#10b981`, touch targets >= 44px).
- Zero external package installation required beyond existing environment.
- Safe atomic file operations: `.env` and `go2rtc.yaml` must be backed up as `.bak` before being modified.
- Multi-region auto-scan (`sg` -> `cn` -> `de` -> `us` -> `i2` -> `ru`).

---

### Task 1: Backend Micro-Module `xiaomi_wizard.py`

**Files:**
- Create: `cctv_dashboard/xiaomi_wizard.py`
- Create: `cctv_dashboard/tests/test_xiaomi_wizard.py`

**Interfaces:**
- Consumes: Standard `urllib.request`, `json`, `Crypto.Cipher.ARC4`, `hashlib`, `os`, `time`.
- Produces: `XiaomiWizardSession` class with methods:
  - `start_qr_session() -> dict`: returns `{"qr_url": str, "login_url": str, "lp_url": str, "timeout": int}`
  - `poll_qr_status() -> dict`: returns `{"state": "waiting"|"authorized"|"expired", "user_id": str}`
  - `discover_cameras() -> dict`: returns `{"region": str, "cameras": list}`
  - `generate_configs(camera_dict: dict, base_dir: str) -> bool`: writes `.env` and `go2rtc.yaml`

- [ ] **Step 1: Write unit tests in `tests/test_xiaomi_wizard.py`**
  - Test session creation and long-polling URL format.
  - Test device parsing and detection of dual-lens vs single-lens.
  - Test config generator writing valid `.env` and `go2rtc.yaml` syntax.
- [ ] **Step 2: Run test to verify initial failure**
  - Run `pytest tests/test_xiaomi_wizard.py`
- [ ] **Step 3: Implement `xiaomi_wizard.py`**
  - Implement QR login handshake (`loginUrl`, `longPolling/token`).
  - Implement Xiaomi Cloud API decryption and multi-region device querying.
  - Implement safe `.env` & `go2rtc.yaml` atomic writing with `.bak` backups.
- [ ] **Step 4: Run test to verify success**
  - Run `pytest tests/test_xiaomi_wizard.py` and ensure 100% pass.
- [ ] **Step 5: Git commit**
  - `git commit -m "feat(wizard): implement xiaomi_wizard backend module with tests"`

---

### Task 2: Integrate Wizard REST API into `server.py`

**Files:**
- Modify: `cctv_dashboard/server.py`
- Create: `cctv_dashboard/tests/test_wizard_api.py`

**Interfaces:**
- Consumes: `XiaomiWizardSession` from `xiaomi_wizard.py`.
- Produces: Endpoints:
  - `GET /api/wizard/check`: returns configured status.
  - `POST /api/wizard/start`: starts QR session.
  - `GET /api/wizard/status`: checks polling status.
  - `GET /api/wizard/devices`: fetches discovered cameras.
  - `POST /api/wizard/save`: applies chosen camera and reloads streams.

- [ ] **Step 1: Write API test in `tests/test_wizard_api.py`**
  - Test `GET /api/wizard/check`.
  - Test `POST /api/wizard/start` mock flow.
- [ ] **Step 2: Run test to verify failure**
  - Run `pytest tests/test_wizard_api.py`
- [ ] **Step 3: Add endpoint handlers in `server.py`**
  - Map routes under `do_GET` and `do_POST`.
  - Wire handlers to `XiaomiWizardSession` singleton instance.
- [ ] **Step 4: Run test to verify success**
  - Run `pytest tests/test_wizard_api.py`.
- [ ] **Step 5: Git commit**
  - `git commit -m "feat(api): expose wizard endpoints in server.py"`

---

### Task 3: Setup Wizard UI Component in `public/index.html`

**Files:**
- Modify: `cctv_dashboard/public/index.html`

**Interfaces:**
- Consumes: `/api/wizard/*` REST endpoints.
- Produces:
  - `#setupWizardModal` DOM structure (Step 1 QR & Link, Step 2 Device Selection, Step 3 Sync Progress).
  - JavaScript logic to handle QR polling, countdown timer, device card rendering, and single-click activation.
  - Navbar button / settings trigger "Hubungkan / Ganti CCTV".

- [ ] **Step 1: Add Setup Wizard Modal HTML markup**
  - Build step progress indicators (`1. Login Xiaomi` -> `2. Pilih Kamera` -> `3. Selesai`).
  - Add QR display area with fallback direct link button.
  - Add camera selection list container.
  - Add loading/sync status indicator.
- [ ] **Step 2: Add CSS styling in `index.html`**
  - Style `.wizard-card`, `.camera-select-card`, `.badge-dual`, `.badge-single`.
  - Ensure mobile layout compliance (full touch targets, no horizontal overflow).
- [ ] **Step 3: Implement client-side JavaScript wizard flow**
  - Check `/api/wizard/check` on startup. If unconfigured, open modal.
  - Polling loop for QR status with countdown and auto-expiration detection.
  - Dynamic rendering of discovered camera cards.
  - Submission handler calling `/api/wizard/save`.
- [ ] **Step 4: Git commit**
  - `git commit -m "feat(ui): add setup wizard modal and interactive onboarding flow"`

---

### Task 4: Dynamic Adaptive UI for Single-Lens vs Dual-Lens

**Files:**
- Modify: `cctv_dashboard/public/index.html`

**Interfaces:**
- Consumes: `CCTV_LENS_MODE` or camera `lens_type` (`single` vs `dual`).
- Produces:
  - In single-lens mode: Hide Lensa 2 video element and switch buttons; expand Lensa 1 to full width.
  - In dual-lens mode: Maintain side-by-side or tabbed dual-lens view.

- [ ] **Step 1: Implement `applyLensMode(mode)` JavaScript function**
  - Dynamically toggle visibility of `#camRightContainer`, lens switch pills, and dual-recording options when `mode === 'single'`.
- [ ] **Step 2: Test both single-lens and dual-lens modes**
  - Verify layout responsiveness and absence of broken stream errors on single-lens mode.
- [ ] **Step 3: Git commit**
  - `git commit -m "feat(ui): add adaptive layout for single-lens vs dual-lens cameras"`

---

### Task 5: End-to-End Verification & Playwright Tests

**Files:**
- Create: `cctv_dashboard/tests/verify_wizard_e2e.py`

**Interfaces:**
- Consumes: Running dashboard at `http://127.0.0.1:8088`.
- Produces: Playwright test assertions and screenshots.

- [ ] **Step 1: Write Playwright test script**
  - Test modal opening via Settings / menu.
  - Verify QR container, countdown, and direct link elements render without JS errors.
  - Test mobile viewport (390×844) and desktop viewport (1920×1080).
  - Capture screenshot of Setup Wizard UI.
- [ ] **Step 2: Run verification test**
  - Run `python3 tests/verify_wizard_e2e.py`.
- [ ] **Step 3: Inspect screenshot and verify 0 console errors**
- [ ] **Step 4: Git commit**
  - `git commit -m "test(wizard): add playwright e2e verification tests"`

---

### Task 6: Final Documentation, Knowledge Graph Update, and Service Verification

**Files:**
- Modify: `cctv_dashboard/README.md`
- Run: `graphify update .`

- [ ] **Step 1: Update README.md with first-run onboarding instructions**
- [ ] **Step 2: Restart services and verify live status**
  - `systemctl restart cctv-dashboard.service`
  - Verify `http://127.0.0.1:8088` is responsive.
- [ ] **Step 3: Run `graphify update .`**
- [ ] **Step 4: Git commit**
  - `git commit -m "docs: update README with setup wizard guide and update knowledge graph"`
