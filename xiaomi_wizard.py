#!/usr/bin/env python3
"""
Xiaomi Cloud Zero-Config Setup Wizard Module
Handles Xiaomi SSO QR Code authentication, multi-region device discovery,
and automatic .env and go2rtc.yaml configuration generation.
"""

import os
import sys
import json
import time
import base64
import random
import hashlib
import hmac
import shutil
import logging
import requests
from Crypto.Cipher import ARC4

logger = logging.getLogger("xiaomi_wizard")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s]: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def detect_lens_type(model: str) -> str:
    """Detect if camera model has dual-lens or single-lens configuration."""
    if not model:
        return "single"
    m_lower = model.lower()
    # Xiaomi CW100 (075ae1), CW700S (075a), or explicitly dual
    if "075a" in m_lower or "dual" in m_lower:
        return "dual"
    return "single"


def generate_env_content(camera: dict) -> str:
    """Generate .env file content from selected camera data."""
    ip = camera.get("ip") or "192.168.1.11"
    port = camera.get("port", 54321)
    token = camera.get("token") or "0" * 32
    did = str(camera.get("did", ""))
    name = camera.get("name") or "Xiaomi CCTV"
    model = camera.get("model") or "chuangmi.camera.075ae1"
    lens_type = camera.get("lens_type") or detect_lens_type(model)
    region = camera.get("region") or "sg"
    user_id = str(camera.get("user_id") or "")
    email = camera.get("email") or ""

    lines = [
        "# ==========================================",
        f"# {name} ({model}) - Auto Configured by Web Wizard",
        "# ==========================================",
        "",
        "# IP Kamera CCTV di jaringan LAN",
        f"CCTV_CAMERA_IP={ip}",
        f"CCTV_CAMERA_PORT={port}",
        "",
        "# Device Token (32-karakter hex didapat dari token extractor)",
        f"CCTV_TOKEN_HEX={token}",
        "",
        "# Device ID (did)",
        f"CCTV_DID={did}",
        f"CCTV_MODEL={model}",
        f"CCTV_LENS_MODE={lens_type}",
        "",
        "# Port Web Dashboard CCTV",
        "CCTV_PORT=8088",
        "",
        "# Endpoint API go2rtc gateway",
        "GO2RTC_API=http://127.0.0.1:1984",
        "",
        "# Endpoint RTSP untuk DVR recorder",
        "RTSP_HOST=127.0.0.1:8554",
        "",
        "# Folder penyimpanan rekaman video",
        "CCTV_STORAGE_DIR=/root/cctv_recordings",
        "",
        "# Kredensial Akun Xiaomi (Otentikasi Cloud)",
        f"XIAOMI_USER_ID={user_id}",
        f"XIAOMI_USER_EMAIL={email}",
        f"XIAOMI_REGION={region}",
        f"CCTV_NAME={name}",
        ""
    ]
    return "\n".join(lines)


def generate_go2rtc_yaml(camera: dict) -> str:
    """Generate go2rtc.yaml configuration from selected camera data."""
    ip = camera.get("ip") or "192.168.1.11"
    did = str(camera.get("did", ""))
    model = camera.get("model") or "chuangmi.camera.075ae1"
    lens_type = camera.get("lens_type") or detect_lens_type(model)
    region = camera.get("region") or "sg"
    user_id = str(camera.get("user_id") or "")
    pass_token = camera.get("pass_token") or ""

    lines = [
        'api:',
        '  listen: ":1984"',
        '  origin: "*"',
        '',
        'rtsp:',
        '  listen: ":8554"',
        '',
        'webrtc:',
        '  listen: ":8555"',
        '',
        'ffmpeg:',
        '  bin: "ffmpeg"',
        '  h264: "-vf cas=0.35 -c:v libx264 -preset:v veryfast -tune:v zerolatency -crf 18 -b:v 4500k -maxrate 6500k -bufsize 8000k -profile:v high -level:v 4.2"',
        '',
        'xiaomi:',
        f'  "{user_id}": {pass_token}',
        '',
        'streams:',
        '  # Lensa Kiri (Primary / Wide Angle - Native 2.5K Ultra HD)',
        '  cctv_lensa_kiri:',
        f'    - xiaomi://{user_id}:{region}@{ip}?did={did}&model={model}&subtype=3',
        '    - ffmpeg:cctv_lensa_kiri#video=h264',
        '  cctv_garasi_kiri:',
        '    - cctv_lensa_kiri',
        '  cctv_garasi_left:',
        '    - cctv_lensa_kiri',
        ''
    ]

    if lens_type == "dual":
        lines.extend([
            '  # Lensa Kanan (Secondary / PTZ Lens - Native 2.5K Ultra HD)',
            '  cctv_lensa_kanan:',
            f'    - xiaomi://{user_id}:{region}@{ip}?did={did}&model={model}&channel=2&subtype=3',
            '    - ffmpeg:cctv_lensa_kanan#video=h264',
            '  cctv_garasi_kanan:',
            '    - cctv_lensa_kanan',
            '  cctv_garasi_right:',
            '    - cctv_lensa_kanan',
            ''
        ])

    return "\n".join(lines)


class XiaomiWizardSession:
    """Manages active QR Code SSO session and device discovery for Setup Wizard."""

    def __init__(self):
        self._session = requests.Session()
        self.state = "idle"  # idle, waiting, authorized, expired, error
        self.user_id = None
        self.pass_token = None
        self._ssecurity = None
        self._cUserId = None
        self.service_token = None
        self._location = None
        self.qr_image_url = None
        self.login_url = None
        self.long_polling_url = None
        self.timeout = 120
        self.created_at = 0
        self.discovered_cameras = []
        self.active_region = "sg"
        self._agent = self.generate_agent()

    @staticmethod
    def generate_agent():
        agent_id = "".join(map(lambda i: chr(i), [random.randint(65, 69) for _ in range(13)]))
        random_text = "".join(map(lambda i: chr(i), [random.randint(97, 122) for _ in range(18)]))
        return f"{random_text}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"

    def start_qr_session(self) -> dict:
        """Initialize Xiaomi QR login session."""
        url = "https://account.xiaomi.com/longPolling/loginUrl"
        data = {
            "_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false",
            "sid": "xiaomiio",
            "serviceParam": "",
            "_locale": "en_GB",
            "_dc": str(int(time.time() * 1000))
        }

        try:
            resp = self._session.get(url, params=data, timeout=10)
            if resp.status_code == 200:
                raw_text = resp.text.replace("&&&START&&&", "").strip()
                res_data = json.loads(raw_text)
                if "qr" in res_data:
                    self.qr_image_url = res_data["qr"]
                    self.login_url = res_data["loginUrl"]
                    self.long_polling_url = res_data["lp"]
                    self.timeout = res_data.get("timeout", 120)
                    self.created_at = time.time()
                    self.state = "waiting"
                    return {
                        "success": True,
                        "qr_url": self.qr_image_url,
                        "login_url": self.login_url,
                        "timeout": self.timeout
                    }
            self.state = "error"
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            self.state = "error"
            logger.error(f"Failed to start QR session: {e}")
            return {"success": False, "error": str(e)}

    def poll_qr_status(self, timeout: float = 3.0) -> dict:
        """Check status of long-polling ticket."""
        if self.state == "authorized":
            return {"state": "authorized", "user_id": self.user_id}

        if not self.long_polling_url:
            return {"state": "idle", "message": "No active session"}

        if self.created_at > 0 and (time.time() - self.created_at > self.timeout):
            self.state = "expired"
            return {"state": "expired", "message": "QR Code has expired"}

        try:
            resp = self._session.get(self.long_polling_url, timeout=timeout)
            if resp.status_code == 200:
                raw_text = resp.text.replace("&&&START&&&", "").strip()
                res_data = json.loads(raw_text)
                self.user_id = str(res_data.get("userId", ""))
                self._ssecurity = res_data.get("ssecurity")
                self._cUserId = res_data.get("cUserId")
                self.pass_token = res_data.get("passToken")
                self._location = res_data.get("location")

                # Fetch service token from sts location
                if self._location:
                    loc_resp = self._session.get(
                        self._location,
                        headers={"content-type": "application/x-www-form-urlencoded"},
                        timeout=8
                    )
                    if loc_resp.status_code == 200:
                        self.service_token = loc_resp.cookies.get("serviceToken", "")

                self.state = "authorized"
                logger.info(f"User {self.user_id} successfully authenticated via QR!")
                return {"state": "authorized", "user_id": self.user_id}
            else:
                return {"state": "waiting", "message": "Waiting for scan and approval"}
        except requests.exceptions.Timeout:
            return {"state": "waiting", "message": "Polling timeout, still waiting"}
        except Exception as e:
            logger.warning(f"Error during poll_qr_status: {e}")
            return {"state": "waiting", "message": str(e)}

    # Xiaomi Cloud API Encryption & Request Helpers
    @staticmethod
    def get_api_url(country: str) -> str:
        return "https://" + ("" if country == "cn" else (country + ".")) + "api.io.mi.com/app"

    def signed_nonce(self, nonce: str) -> str:
        hash_object = hashlib.sha256(base64.b64decode(self._ssecurity) + base64.b64decode(nonce))
        return base64.b64encode(hash_object.digest()).decode("utf-8")

    @staticmethod
    def generate_nonce(millis: int) -> str:
        nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder="big")
        return base64.b64encode(nonce_bytes).decode()

    @staticmethod
    def encrypt_rc4(password: str, payload: str) -> str:
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return base64.b64encode(r.encrypt(payload.encode())).decode()

    @staticmethod
    def decrypt_rc4(password: str, payload: str) -> bytes:
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return r.encrypt(base64.b64decode(payload))

    @staticmethod
    def generate_enc_signature(url: str, method: str, signed_nonce: str, params: dict) -> str:
        signature_params = [str(method).upper(), url.split("com")[1].replace("/app/", "/")]
        for k, v in params.items():
            signature_params.append(f"{k}={v}")
        signature_params.append(signed_nonce)
        signature_string = "&".join(signature_params)
        return base64.b64encode(hashlib.sha1(signature_string.encode("utf-8")).digest()).decode()

    def generate_enc_params(self, url: str, method: str, signed_nonce: str, nonce: str, params: dict) -> dict:
        params["rc4_hash__"] = self.generate_enc_signature(url, method, signed_nonce, params)
        for k, v in list(params.items()):
            params[k] = self.encrypt_rc4(signed_nonce, v)
        params.update({
            "signature": self.generate_enc_signature(url, method, signed_nonce, params),
            "ssecurity": self._ssecurity,
            "_nonce": nonce,
        })
        return params

    def execute_api_call_encrypted(self, url: str, params: dict):
        if not self._ssecurity or not self.service_token:
            return None
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }
        cookies = {
            "userId": str(self.user_id),
            "yetAnotherServiceToken": str(self.service_token),
            "serviceToken": str(self.service_token),
            "locale": "en_GB",
            "timezone": "GMT+07:00",
            "channel": "MI_APP_STORE"
        }
        millis = round(time.time() * 1000)
        nonce = self.generate_nonce(millis)
        signed_nonce = self.signed_nonce(nonce)
        fields = self.generate_enc_params(url, "POST", signed_nonce, nonce, params)
        try:
            resp = self._session.post(url, headers=headers, cookies=cookies, params=fields, timeout=10)
            if resp.status_code == 200:
                decoded = self.decrypt_rc4(self.signed_nonce(fields["_nonce"]), resp.text)
                return json.loads(decoded.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error in execute_api_call_encrypted: {e}")
        return None

    def get_homes(self, country: str):
        url = self.get_api_url(country) + "/v2/homeroom/gethome"
        params = {"data": '{"fg": true, "fetch_share": true, "fetch_share_dev": true, "limit": 300, "app_ver": 7}'}
        return self.execute_api_call_encrypted(url, params)

    def get_devices(self, country: str, home_id, owner_id):
        url = self.get_api_url(country) + "/v2/home/home_device_list"
        params = {
            "data": f'{{"home_owner": {owner_id}, "home_id": {home_id}, "limit": 200, "get_split_device": true, "support_smart_home": true}}'
        }
        return self.execute_api_call_encrypted(url, params)

    def discover_cameras(self, regions: list = None) -> dict:
        """Scan Xiaomi account across regions (defaults to sg -> cn -> de -> us)."""
        if not self.user_id or not self.service_token:
            return {"success": False, "error": "Not authenticated with Xiaomi Cloud", "cameras": []}

        if regions is None:
            regions = ["sg", "cn", "de", "us", "i2", "ru"]

        all_cameras = []
        found_region = None

        for reg in regions:
            logger.info(f"Scanning Xiaomi region: {reg}...")
            homes_resp = self.get_homes(reg)
            if not homes_resp or "result" not in homes_resp or not homes_resp["result"]:
                continue

            home_list = homes_resp["result"].get("homelist", [])
            for h in home_list:
                home_id = h.get("id")
                dev_resp = self.get_devices(reg, home_id, self.user_id)
                if not dev_resp or "result" not in dev_resp:
                    continue
                dev_info = dev_resp["result"].get("device_info", []) or []
                for d in dev_info:
                    model = d.get("model", "")
                    name = d.get("name", "")
                    # Filter for camera devices
                    if "camera" in model.lower() or "camera" in name.lower() or "cctv" in name.lower():
                        lens_type = detect_lens_type(model)
                        all_cameras.append({
                            "name": name,
                            "did": str(d.get("did", "")),
                            "model": model,
                            "ip": d.get("localip", ""),
                            "token": d.get("token", ""),
                            "lens_type": lens_type,
                            "is_online": bool(d.get("isOnline", False)),
                            "region": reg
                        })

            if all_cameras:
                found_region = reg
                break  # Prioritized region found cameras!

        self.discovered_cameras = all_cameras
        self.active_region = found_region or "sg"
        return {
            "success": True,
            "region": self.active_region,
            "cameras": all_cameras
        }

    def apply_camera_config(self, camera_data: dict, base_dir: str = None) -> bool:
        """Apply chosen camera configuration to .env and go2rtc.yaml safely with backups."""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        env_path = os.path.join(base_dir, ".env")
        yaml_path = os.path.join(base_dir, "go2rtc.yaml")

        camera_data["user_id"] = self.user_id or camera_data.get("user_id")
        camera_data["pass_token"] = self.pass_token or camera_data.get("pass_token")
        camera_data["region"] = camera_data.get("region") or self.active_region

        new_env = generate_env_content(camera_data)
        new_yaml = generate_go2rtc_yaml(camera_data)

        # Atomic backup and write
        try:
            if os.path.exists(env_path):
                shutil.copyfile(env_path, env_path + ".bak")
            with open(env_path + ".tmp", "w", encoding="utf-8") as f:
                f.write(new_env)
            os.replace(env_path + ".tmp", env_path)

            if os.path.exists(yaml_path):
                shutil.copyfile(yaml_path, yaml_path + ".bak")
            with open(yaml_path + ".tmp", "w", encoding="utf-8") as f:
                f.write(new_yaml)
            os.replace(yaml_path + ".tmp", yaml_path)

            logger.info("Successfully updated .env and go2rtc.yaml with backup.")
            return True
        except Exception as e:
            logger.error(f"Failed to apply config: {e}")
            return False


# Global singleton instance for application use
wizard_session = XiaomiWizardSession()
