#!/usr/bin/env python3
import http.server
import socketserver
import json
import socket
import hashlib
import time
import os
import sys
import shutil
import threading
import subprocess
import urllib.request
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val

load_env(os.path.join(BASE_DIR, ".env"))

from recorder import recorder
from xiaomi_wizard import wizard_session
from youtube_streamer import youtube_streamer

CAMERA_IP = os.environ.get("CCTV_CAMERA_IP", "192.168.1.100")
CAMERA_PORT = int(os.environ.get("CCTV_CAMERA_PORT", 54321))
TOKEN_HEX = os.environ.get("CCTV_TOKEN_HEX", "0" * 32)
TOKEN = bytes.fromhex(TOKEN_HEX)
DID = os.environ.get("CCTV_DID", "0")
PORT = int(os.environ.get("CCTV_PORT", 8088))
GO2RTC_API = os.environ.get("GO2RTC_API", "http://127.0.0.1:1984")
CCTV_NAME = os.environ.get("CCTV_NAME", "Xiaomi CW100 Dual")
XIAOMI_USER_ID = os.environ.get("XIAOMI_USER_ID", "-")
XIAOMI_USER_EMAIL = os.environ.get("XIAOMI_USER_EMAIL", "Connected Account")
STREAM_LEFT = os.environ.get("CCTV_STREAM_LEFT", "cctv_lensa_kiri")
STREAM_RIGHT = os.environ.get("CCTV_STREAM_RIGHT", "cctv_lensa_kanan")

_status_cache = {"data": None, "timestamp": 0}
_status_lock = threading.Lock()

_advanced_cache = {"data": None, "timestamp": 0}
_advanced_lock = threading.Lock()

def invalidate_status_cache():
    with _status_lock:
        _status_cache["timestamp"] = 0

def invalidate_advanced_cache():
    with _advanced_lock:
        _advanced_cache["timestamp"] = 0

def check_stalled_go2rtc_sockets(threshold_bytes=250000):
    try:
        proc = subprocess.run(["ss", "-tn", "( sport = :1984 or sport = :1985 )"], capture_output=True, text=True, timeout=2)
        if proc.returncode != 0:
            return False
        for line in proc.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "ESTAB":
                try:
                    send_q = int(parts[2])
                    if send_q > threshold_bytes:
                        return True
                except ValueError:
                    pass
    except Exception:
        pass
    return False

def _stream_watchdog_loop():
    while True:
        time.sleep(10)
        try:
            if check_stalled_go2rtc_sockets():
                print("[Stream Watchdog] Stalled consumer socket detected (Send-Q buffer clogged). Flushing go2rtc to release camera P2P slots.", file=sys.stderr)
                req = urllib.request.Request(f"{GO2RTC_API}/api/restart", data=b"", method="POST")
                urllib.request.urlopen(req, timeout=3)
                invalidate_status_cache()
                invalidate_advanced_cache()
        except Exception:
            pass

def refresh_runtime_config():
    global CAMERA_IP, CAMERA_PORT, TOKEN_HEX, TOKEN, DID, CCTV_NAME, XIAOMI_USER_ID, XIAOMI_USER_EMAIL
    load_env(os.path.join(BASE_DIR, ".env"))
    CAMERA_IP = os.environ.get("CCTV_CAMERA_IP", "192.168.1.100")
    CAMERA_PORT = int(os.environ.get("CCTV_CAMERA_PORT", 54321))
    TOKEN_HEX = os.environ.get("CCTV_TOKEN_HEX", "0" * 32)
    TOKEN = bytes.fromhex(TOKEN_HEX)
    DID = os.environ.get("CCTV_DID", "0")
    CCTV_NAME = os.environ.get("CCTV_NAME", "Xiaomi CW100 Dual")
    XIAOMI_USER_ID = os.environ.get("XIAOMI_USER_ID", "-")
    XIAOMI_USER_EMAIL = os.environ.get("XIAOMI_USER_EMAIL", "Connected Account")

def get_wizard_configuration_status():
    cam_ip = os.environ.get("CCTV_CAMERA_IP", "").strip()
    token = os.environ.get("CCTV_TOKEN_HEX", "").strip()
    did = os.environ.get("CCTV_DID", "").strip()
    is_valid = bool(cam_ip and cam_ip != "192.168.1.100" and token and token != "0"*32 and did)
    return {
        "configured": is_valid,
        "camera": {
            "ip": cam_ip,
            "did": did,
            "name": os.environ.get("CCTV_NAME", "Xiaomi CCTV"),
            "model": os.environ.get("CCTV_MODEL", "chuangmi.camera.075ae1"),
            "lens_type": os.environ.get("CCTV_LENS_MODE", "dual"),
            "region": os.environ.get("XIAOMI_REGION", "sg")
        }
    }

ADVANCED_PROP_MAP = {
    # Tampilan & Optik
    "image_flip": {"siid": 2, "piid": 4, "type": int},
    "time_watermark": {"siid": 2, "piid": 5, "type": bool},
    "wdr_mode": {"siid": 2, "piid": 6, "type": bool},
    "glimmer_color": {"siid": 2, "piid": 7, "type": bool},
    "distortion_correction": {"siid": 2, "piid": 14, "type": bool},
    "ai_frame": {"siid": 2, "piid": 17, "type": bool},

    # Lampu & Audio Hardware
    "status_led": {"siid": 4, "piid": 1, "type": bool},
    "spotlight_on": {"siid": 16, "piid": 1, "type": bool},
    "spotlight_brightness": {"siid": 16, "piid": 2, "type": int},
    "speaker_volume": {"siid": 6, "piid": 1, "type": int},
    "speaker_mute": {"siid": 6, "piid": 2, "type": bool},
    "warning_light_switch": {"siid": 20, "piid": 3, "type": bool},
    "warning_audio_switch": {"siid": 20, "piid": 4, "type": bool},
    "warning_light_mode": {"siid": 20, "piid": 6, "type": int},

    # AI & Sensitivitas
    "motion_switch": {"siid": 5, "piid": 1, "type": bool},
    "motion_sensitivity": {"siid": 5, "piid": 3, "type": int},
    "human_detection": {"siid": 8, "piid": 6, "type": bool},
    "car_detection": {"siid": 8, "piid": 21, "type": bool},
    "ai_sensitivity": {"siid": 8, "piid": 28, "type": int},

    # SD Card Rekaman Mode
    "sd_recording_mode": {"siid": 2, "piid": 11, "type": int},
}

def is_device_authenticated():
    status = get_wizard_configuration_status()
    return bool(status.get("configured", False) and TOKEN_HEX and TOKEN_HEX != "0" * 32)

def get_advanced_camera_status():
    now = time.time()
    with _advanced_lock:
        if _advanced_cache["data"] is not None and (now - _advanced_cache["timestamp"]) < 4.0:
            return _advanced_cache["data"]

    prop_queries = [
        {"key": "image_flip", "siid": 2, "piid": 4},
        {"key": "time_watermark", "siid": 2, "piid": 5},
        {"key": "wdr_mode", "siid": 2, "piid": 6},
        {"key": "glimmer_color", "siid": 2, "piid": 7},
        {"key": "distortion_correction", "siid": 2, "piid": 14},
        {"key": "ai_frame", "siid": 2, "piid": 17},
        {"key": "sd_recording_mode", "siid": 2, "piid": 11},
        {"key": "status_led", "siid": 4, "piid": 1},
        {"key": "motion_switch", "siid": 5, "piid": 1},
        {"key": "motion_sensitivity", "siid": 5, "piid": 3},
        {"key": "speaker_volume", "siid": 6, "piid": 1},
        {"key": "speaker_mute", "siid": 6, "piid": 2},
        {"key": "human_detection", "siid": 8, "piid": 6},
        {"key": "car_detection", "siid": 8, "piid": 21},
        {"key": "ai_sensitivity", "siid": 8, "piid": 28},
        {"key": "spotlight_on", "siid": 16, "piid": 1},
        {"key": "spotlight_brightness", "siid": 16, "piid": 2},
        {"key": "warning_light_switch", "siid": 20, "piid": 3},
        {"key": "warning_audio_switch", "siid": 20, "piid": 4},
        {"key": "warning_light_mode", "siid": 20, "piid": 6},
        {"key": "sd_status", "siid": 3, "piid": 1},
        {"key": "sd_total", "siid": 3, "piid": 2},
        {"key": "sd_free", "siid": 3, "piid": 3},
        {"key": "sd_used", "siid": 3, "piid": 4},
    ]

    out = {}
    chunk_size = 4
    for i in range(0, len(prop_queries), chunk_size):
        chunk = prop_queries[i:i+chunk_size]
        req = [{"did": DID, "siid": p["siid"], "piid": p["piid"]} for p in chunk]
        try:
            res = send_miio_rpc("get_properties", req, timeout=2.0)
            for p, item in zip(chunk, res.get("result", [])):
                if item.get("code") == 0:
                    out[p["key"]] = item.get("value")
        except Exception:
            pass
        time.sleep(0.04)

    sd_status = out.get("sd_status")
    sd_status_map = {
        0: "Normal",
        1: "Tidak Terdeteksi",
        2: "Penyimpanan Penuh",
        3: "Rusak / Error",
        4: "Sedang Diformat",
        5: "Dikeluarkan (Ejected)",
        6: "Sedang Diperbaiki",
        8: "Belum Diinisialisasi"
    }
    sd_rec_map = {
        0: "Jangan Rekam",
        1: "Rekam Saat Gerakan",
        2: "Rekam Terus-Menerus"
    }
    total_kb = out.get("sd_total") or 0
    free_kb = out.get("sd_free") or 0
    used_kb = out.get("sd_used") or (total_kb - free_kb if total_kb >= free_kb else 0)

    data = {
        "image_flip": out.get("image_flip", 0),
        "time_watermark": bool(out.get("time_watermark", True)),
        "wdr_mode": bool(out.get("wdr_mode", True)),
        "glimmer_color": bool(out.get("glimmer_color", True)),
        "distortion_correction": bool(out.get("distortion_correction", True)),
        "ai_frame": bool(out.get("ai_frame", False)),
        "status_led": bool(out.get("status_led", True)),
        "spotlight_on": bool(out.get("spotlight_on", False)),
        "spotlight_brightness": int(out.get("spotlight_brightness", 100)),
        "speaker_volume": int(out.get("speaker_volume", 100)),
        "speaker_mute": bool(out.get("speaker_mute", False)),
        "warning_light_switch": bool(out.get("warning_light_switch", True)),
        "warning_audio_switch": bool(out.get("warning_audio_switch", False)),
        "warning_light_mode": int(out.get("warning_light_mode", 3)),
        "motion_switch": bool(out.get("motion_switch", True)),
        "motion_sensitivity": int(out.get("motion_sensitivity", 1)),
        "human_detection": bool(out.get("human_detection", True)),
        "car_detection": bool(out.get("car_detection", False)),
        "ai_sensitivity": int(out.get("ai_sensitivity", 1)),
        "sdcard": {
            "status": sd_status if sd_status is not None else 1,
            "status_text": sd_status_map.get(sd_status, "Tidak Diketahui"),
            "total_mb": round(total_kb / 1024, 1),
            "free_mb": round(free_kb / 1024, 1),
            "used_mb": round(used_kb / 1024, 1),
            "recording_mode": out.get("sd_recording_mode", 0),
            "recording_mode_text": sd_rec_map.get(out.get("sd_recording_mode", 0), "Jangan Rekam")
        }
    }
    with _advanced_lock:
        _advanced_cache["data"] = data
        _advanced_cache["timestamp"] = now
    return data

def send_miio_rpc(method, params, timeout=2.5):
    hello = bytes.fromhex("21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(hello, (CAMERA_IP, CAMERA_PORT))
    resp, _ = sock.recvfrom(1024)
    dev_id, stamp = resp[8:12], resp[12:16]

    key = hashlib.md5(TOKEN).digest()
    iv = hashlib.md5(key + TOKEN).digest()

    req = {"id": int(time.time() * 1000) % 100000, "method": method, "params": params}
    payload = json.dumps(req).encode()
    pad_len = 16 - (len(payload) % 16)
    padded = payload + bytes([pad_len] * pad_len)
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(padded)

    length = 32 + len(encrypted)
    header = bytes.fromhex("2131") + length.to_bytes(2, "big") + bytes(4) + dev_id + stamp
    checksum = hashlib.md5(header[:16] + TOKEN + encrypted).digest()
    packet = header[:16] + checksum + encrypted

    sock.sendto(packet, (CAMERA_IP, CAMERA_PORT))
    res_data, _ = sock.recvfrom(4096)
    decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(res_data[32:])
    sock.close()
    return json.loads(decrypted[:-decrypted[-1]].decode())

class CCTVHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.handle_api_status()
        elif parsed.path == "/api/wizard/check":
            self.send_json(get_wizard_configuration_status())
        elif parsed.path == "/api/wizard/status":
            self.send_json(wizard_session.poll_qr_status())
        elif parsed.path == "/api/wizard/devices":
            devices = wizard_session.discover_cameras()
            if not devices.get("cameras"):
                status = get_wizard_configuration_status()
                if status.get("configured") and status.get("camera"):
                    cam = status["camera"]
                    devices = {
                        "success": True,
                        "cameras": [{
                            "name": CCTV_NAME or "Xiaomi CCTV",
                            "did": str(DID),
                            "model": cam.get("model", "chuangmi.camera.075ae1"),
                            "ip": CAMERA_IP,
                            "token": TOKEN_HEX,
                            "lens_type": cam.get("lens_type", "dual"),
                            "region": os.environ.get("XIAOMI_REGION", "sg")
                        }]
                    }
            self.send_json(devices)
        elif parsed.path == "/api/ping":
            self.handle_api_ping()
        elif parsed.path == "/api/auth/status":
            self.handle_auth_status()
        elif parsed.path.startswith("/api/snapshot/"):
            self.handle_snapshot(parsed.path)
        elif parsed.path in ("/settings", "/settings/"):
            self.path = "/settings.html"
            super().do_GET()
        elif parsed.path == "/api/camera/advanced":
            if not is_device_authenticated():
                self.send_json({"success": False, "authenticated": False, "error": "Autentikasi akun Xiaomi diperlukan"}, status=401)
                return
            adv_data = get_advanced_camera_status()
            self.send_json({"success": True, "authenticated": True, "data": adv_data})
        elif parsed.path == "/api/record/status":
            self.send_json(recorder.get_status())
        elif parsed.path == "/api/youtube/status":
            self.send_json(youtube_streamer.get_status())
        elif parsed.path == "/api/recordings":
            self.send_json({
                "recordings": recorder.list_recordings(),
                "status": recorder.get_status()
            })
        elif parsed.path.startswith("/api/recordings/") and parsed.path.endswith("/stream"):
            # Format: /api/recordings/<filename>/stream
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 4:
                filename = parts[2]
                self.handle_video_stream(filename, as_attachment=False)
            else:
                self.send_error(400, "Invalid stream URL")
        elif parsed.path.startswith("/api/recordings/") and parsed.path.endswith("/download"):
            # Format: /api/recordings/<filename>/download
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 4:
                filename = parts[2]
                self.handle_video_stream(filename, as_attachment=True)
            else:
                self.send_error(400, "Invalid download URL")
        else:
            super().do_GET()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/recordings/"):
            filename = parsed.path.replace("/api/recordings/", "").strip("/")
            success, msg = recorder.delete_recording(filename)
            self.send_json({"success": success, "message": msg}, status=200 if success else 400)
        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except:
            data = {}

        if parsed.path == "/api/control/light":
            state = bool(data.get("state", False))
            res = send_miio_rpc("set_properties", [{"did": DID, "siid": 16, "piid": 1, "value": state}])
            invalidate_status_cache()
            self.send_json({"success": True, "result": res, "state": state})

        elif parsed.path == "/api/control/power":
            state = bool(data.get("state", True))
            res = send_miio_rpc("set_properties", [{"did": DID, "siid": 2, "piid": 1, "value": state}])
            invalidate_status_cache()
            self.send_json({"success": True, "result": res, "state": state})

        elif parsed.path == "/api/control/nightshot":
            val = int(data.get("value", 2))
            res = send_miio_rpc("set_properties", [{"did": DID, "siid": 2, "piid": 3, "value": val}])
            invalidate_status_cache()
            self.send_json({"success": True, "result": res, "value": val})

        elif parsed.path == "/api/action/p2p":
            res = send_miio_rpc("action", {"did": DID, "siid": 9, "aiid": 1, "in": []})
            self.send_json({"success": True, "result": res})

        elif parsed.path == "/api/action/reboot":
            res = send_miio_rpc("action", {"did": DID, "siid": 2, "aiid": 2, "in": []})
            invalidate_status_cache()
            self.send_json({"success": True, "result": res})

        elif parsed.path == "/api/control/siren":
            res = send_miio_rpc("action", {"did": DID, "siid": 20, "aiid": 1, "in": []})
            self.send_json({"success": True, "result": res})

        elif parsed.path == "/api/control/ai":
            prop_type = data.get("type", "")
            val = bool(data.get("value", False))
            if prop_type == "motion":
                res = send_miio_rpc("set_properties", [{"did": DID, "siid": 5, "piid": 1, "value": val}])
            elif prop_type == "human":
                res = send_miio_rpc("set_properties", [{"did": DID, "siid": 8, "piid": 6, "value": val}])
            elif prop_type == "car":
                res = send_miio_rpc("set_properties", [{"did": DID, "siid": 8, "piid": 21, "value": val}])
            else:
                res = None
            invalidate_status_cache()
            self.send_json({"success": True, "result": res, "type": prop_type, "value": val})

        elif parsed.path == "/api/control/ptz":
            self.send_json({"success": False, "message": "Kamera Xiaomi CW100 bertipe Fixed Dual-Lens (tanpa motor mekanis PTZ)"})

        elif parsed.path == "/api/telegram/test":
            token = data.get("bot_token", "").strip()
            chat_id = data.get("chat_id", "").strip()
            if not token or not chat_id:
                self.send_json({"success": False, "error": "Token dan Chat ID Telegram wajib diisi"})
            else:
                try:
                    with urllib.request.urlopen(f"{GO2RTC_API}/api/frame.jpeg?src=cctv_garasi_kiri", timeout=6) as resp:
                        img_bytes = resp.read()

                    boundary = "----TelegramFormBoundaryCCTV789"
                    parts = []
                    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode())
                    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n[ALERT] Notifikasi Snapshot CCTV Xiaomi CW100\nWaktu: {time.strftime('%d %b %Y %H:%M:%S')}\nStatus: Pemantauan Aktif\r\n".encode())
                    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"cctv_snapshot.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + img_bytes + b"\r\n")
                    parts.append(f"--{boundary}--\r\n".encode())
                    req_body = b"".join(parts)

                    t_req = urllib.request.Request(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data=req_body,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
                    )
                    with urllib.request.urlopen(t_req, timeout=12) as t_resp:
                        t_data = json.loads(t_resp.read().decode())
                        self.send_json({"success": True, "telegram": t_data})
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)})

        elif parsed.path == "/api/record/timelapse":
            lens = data.get("lens", "left")
            ok, msg = recorder.generate_timelapse(lens)
            self.send_json({"success": ok, "filename": msg if ok else None, "error": None if ok else msg})

        # DVR / Recording Endpoints
        elif parsed.path == "/api/record/start":
            lens = data.get("lens", "both")
            res = recorder.start_manual(lens)
            self.send_json({"success": True, "result": res, "status": recorder.get_status()})

        elif parsed.path == "/api/record/stop":
            lens = data.get("lens", "both")
            res = recorder.stop_manual(lens)
            self.send_json({"success": True, "result": res, "status": recorder.get_status()})

        elif parsed.path == "/api/record/settings":
            new_status = recorder.update_config(data)
            self.send_json({"success": True, "status": new_status})

        elif parsed.path == "/api/recordings/delete":
            filename = data.get("filename", "")
            success, msg = recorder.delete_recording(filename)
            self.send_json({"success": success, "message": msg, "status": recorder.get_status()})

        # Xiaomi Auth Endpoints
        elif parsed.path == "/api/auth/login":
            username = data.get("username", "")
            password = data.get("password", "")
            payload = f"username={urllib.parse.quote(username)}&password={urllib.parse.quote(password)}".encode()
            req = urllib.request.Request(f"{GO2RTC_API}/api/xiaomi", data=payload, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body_resp = resp.read().decode("utf-8")
                    self.send_json({"status": resp.status, "response": body_resp})
            except urllib.error.HTTPError as e:
                body_resp = e.read().decode("utf-8")
                try:
                    parsed_err = json.loads(body_resp)
                except:
                    parsed_err = {"raw": body_resp}
                self.send_json({"status": e.code, "error": parsed_err})
            except Exception as e:
                self.send_json({"status": 500, "error": str(e)})

        elif parsed.path == "/api/auth/verify_otp":
            code = data.get("code", "").strip()
            payload = f"verify={urllib.parse.quote(code)}".encode()
            req = urllib.request.Request(f"{GO2RTC_API}/api/xiaomi", data=payload, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self.send_json({"success": True, "status": resp.status})
            except urllib.error.HTTPError as e:
                self.send_json({"success": False, "status": e.code, "error": e.read().decode("utf-8")})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif parsed.path == "/api/wizard/start":
            self.send_json(wizard_session.start_qr_session())

        elif parsed.path == "/api/wizard/save":
            did = str(data.get("did", "")).strip()
            custom_ip = data.get("ip", "").strip()
            cam_info = None
            for c in wizard_session.discovered_cameras:
                if str(c.get("did")) == did:
                    cam_info = dict(c)
                    break
            if not cam_info:
                cam_info = {
                    "did": did,
                    "ip": custom_ip or data.get("ip", "192.168.1.11"),
                    "token": data.get("token", "0"*32),
                    "name": data.get("name", "Xiaomi CCTV"),
                    "model": data.get("model", "chuangmi.camera.075ae1"),
                    "lens_type": data.get("lens_type", "dual"),
                    "region": data.get("region", wizard_session.active_region)
                }
            if custom_ip:
                cam_info["ip"] = custom_ip

            ok = wizard_session.apply_camera_config(cam_info, base_dir=BASE_DIR)
            if ok:
                refresh_runtime_config()
                try:
                    req = urllib.request.Request(f"{GO2RTC_API}/api/restart", data=b"", method="POST")
                    urllib.request.urlopen(req, timeout=3)
                except:
                    pass
                self.send_json({"success": True, "message": "Konfigurasi kamera berhasil disimpan dan diterapkan!", "camera": cam_info})
            else:
                self.send_json({"success": False, "error": "Gagal menyimpan konfigurasi kamera"}, status=500)

        elif parsed.path == "/api/auth/reload_streams":
            try:
                with urllib.request.urlopen(f"{GO2RTC_API}/api/streams", timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.send_json({"success": True, "streams": data})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif parsed.path == "/api/youtube/start":
            stream_key = data.get("stream_key")
            lens = data.get("lens")
            quality = data.get("quality")
            silent_audio = data.get("silent_audio")
            auto_start = data.get("auto_start")
            success, msg = youtube_streamer.start(
                stream_key=stream_key,
                lens=lens,
                quality=quality,
                silent_audio=silent_audio,
                auto_start=auto_start
            )
            self.send_json({"success": success, "message": msg, "status": youtube_streamer.get_status()})

        elif parsed.path == "/api/youtube/stop":
            success, msg = youtube_streamer.stop()
            self.send_json({"success": success, "message": msg, "status": youtube_streamer.get_status()})

        elif parsed.path == "/api/youtube/config":
            if "stream_key" in data and data["stream_key"]:
                youtube_streamer.config["stream_key"] = data["stream_key"].strip()
            if "lens" in data:
                youtube_streamer.config["lens"] = data["lens"]
            if "quality" in data:
                youtube_streamer.config["quality"] = data["quality"]
            if "silent_audio" in data:
                youtube_streamer.config["silent_audio"] = bool(data["silent_audio"])
            if "auto_start" in data:
                youtube_streamer.config["auto_start"] = bool(data["auto_start"])
            youtube_streamer.save_config()
            self.send_json({"success": True, "status": youtube_streamer.get_status()})

        elif parsed.path == "/api/streams/release":
            try:
                req = urllib.request.Request(f"{GO2RTC_API}/api/restart", data=b"", method="POST")
                urllib.request.urlopen(req, timeout=3)
                invalidate_status_cache()
                invalidate_advanced_cache()
                self.send_json({"success": True, "message": "Semua sesi streaming kamera berhasil dilepas secara instan."})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/camera/advanced":
            if not is_device_authenticated():
                self.send_json({"success": False, "authenticated": False, "error": "Autentikasi akun Xiaomi diperlukan"}, status=401)
                return
            prop_name = str(data.get("property", "")).strip()
            if prop_name not in ADVANCED_PROP_MAP:
                self.send_json({"success": False, "error": f"Properti tidak dikenal: {prop_name}"}, status=400)
                return
            prop_info = ADVANCED_PROP_MAP[prop_name]
            raw_val = data.get("value")
            try:
                target_val = bool(raw_val) if prop_info["type"] is bool else int(raw_val)
            except Exception as e:
                self.send_json({"success": False, "error": f"Nilai tidak valid: {e}"}, status=400)
                return

            res = send_miio_rpc("set_properties", [{
                "did": DID,
                "siid": prop_info["siid"],
                "piid": prop_info["piid"],
                "value": target_val
            }])
            invalidate_advanced_cache()
            invalidate_status_cache()
            self.send_json({
                "success": True,
                "authenticated": True,
                "property": prop_name,
                "value": target_val,
                "result": res
            })

        elif parsed.path == "/api/camera/sdcard":
            if not is_device_authenticated():
                self.send_json({"success": False, "authenticated": False, "error": "Autentikasi akun Xiaomi diperlukan"}, status=401)
                return
            action = str(data.get("action", "")).strip()
            if action == "format":
                res = send_miio_rpc("action", {"did": DID, "siid": 3, "aiid": 1, "in": []})
                invalidate_advanced_cache()
                self.send_json({"success": True, "authenticated": True, "action": "format", "result": res})
            elif action == "eject":
                res = send_miio_rpc("action", {"did": DID, "siid": 3, "aiid": 2, "in": []})
                invalidate_advanced_cache()
                self.send_json({"success": True, "authenticated": True, "action": "eject", "result": res})
            elif action == "set_mode":
                try:
                    mode = int(data.get("mode", 0))
                except:
                    mode = 0
                res = send_miio_rpc("set_properties", [{"did": DID, "siid": 2, "piid": 11, "value": mode}])
                invalidate_advanced_cache()
                self.send_json({"success": True, "authenticated": True, "action": "set_mode", "mode": mode, "result": res})
            else:
                self.send_json({"success": False, "authenticated": True, "error": f"Aksi MicroSD tidak valid: {action}"}, status=400)

        else:
            self.send_error(404, "Endpoint not found")

    def handle_video_stream(self, filename, as_attachment=False):
        clean_name = os.path.basename(filename)
        if clean_name != filename or not filename.endswith(".mp4"):
            self.send_error(400, "Invalid filename")
            return

        storage_dir = recorder.config["storage_dir"]
        filepath = os.path.join(storage_dir, clean_name)
        if not os.path.exists(filepath):
            self.send_error(404, "Recording not found")
            return

        try:
            file_size = os.path.getsize(filepath)
        except Exception as e:
            self.send_error(500, f"Cannot stat file: {e}")
            return

        if as_attachment:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Disposition", f'attachment; filename="{clean_name}"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(filepath, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        range_header = self.headers.get("Range")
        if range_header:
            try:
                byte_range = range_header.strip().split("=")[1]
                parts = byte_range.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
            except Exception:
                start = 0
                end = file_size - 1

            if start >= file_size or end >= file_size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            chunk_length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(chunk_length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = chunk_length
                chunk_size = 64 * 1024
                while remaining > 0:
                    read_bytes = min(remaining, chunk_size)
                    buf = f.read(read_bytes)
                    if not buf:
                        break
                    try:
                        self.wfile.write(buf)
                    except BrokenPipeError:
                        break
                    remaining -= len(buf)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(filepath, "rb") as f:
                shutil.copyfileobj(f, self.wfile)

    def handle_api_status(self):
        now = time.time()
        with _status_lock:
            if _status_cache["data"] is not None and (now - _status_cache["timestamp"]) < 4.0:
                self.send_json(_status_cache["data"])
                return

        try:
            info = send_miio_rpc("miIO.info", [])
            props = send_miio_rpc("get_properties", [
                {"did": DID, "siid": 2, "piid": 1},   # Power
                {"did": DID, "siid": 16, "piid": 1},  # Light
                {"did": DID, "siid": 2, "piid": 3},   # Nightshot
                {"did": DID, "siid": 9, "piid": 1},   # Video Codec
                {"did": DID, "siid": 9, "piid": 9},   # Resolution
                {"did": DID, "siid": 5, "piid": 1},   # Motion Detection
                {"did": DID, "siid": 8, "piid": 6},   # Human Detection
                {"did": DID, "siid": 8, "piid": 21},  # Car Detection
            ])
            payload = {
                "online": True,
                "info": info.get("result", {}),
                "properties": props.get("result", []),
                "timestamp": now
            }
            with _status_lock:
                _status_cache["data"] = payload
                _status_cache["timestamp"] = now
            self.send_json(payload)
        except Exception as e:
            self.send_json({"online": False, "error": str(e)}, status=500)

    def handle_api_ping(self):
        start = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.0)
            s.sendto(bytes.fromhex("21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), (CAMERA_IP, CAMERA_PORT))
            s.recvfrom(1024)
            s.close()
            rtt_ms = round((time.time() - start) * 1000, 2)
            self.send_json({"alive": True, "rtt_ms": rtt_ms})
        except Exception as e:
            self.send_json({"alive": False, "error": str(e)}, status=500)

    def handle_auth_status(self):
        try:
            with urllib.request.urlopen(f"{GO2RTC_API}/api/config", timeout=3) as resp:
                cfg_text = resp.read().decode("utf-8")
            has_xiaomi = "xiaomi:" in cfg_text and "V1:" in cfg_text
            self.send_json({
                "authenticated": has_xiaomi,
                "user_id": XIAOMI_USER_ID,
                "email": XIAOMI_USER_EMAIL,
                "region": os.environ.get("XIAOMI_REGION", "sg"),
                "did": DID,
                "model": "chuangmi.camera.075ae1",
                "cctv_name": CCTV_NAME,
                "streams": {
                    "kiri": STREAM_LEFT,
                    "kanan": STREAM_RIGHT
                }
            })
        except Exception as e:
            self.send_json({"authenticated": False, "error": str(e)})

    def handle_snapshot(self, path):
        stream_name = STREAM_RIGHT if "right" in path or "kanan" in path else STREAM_LEFT
        enhance = "enhance=1" in path or "enhance=true" in path or "clarity=1" in path
        try:
            with urllib.request.urlopen(f"{GO2RTC_API}/api/frame.jpeg?src={stream_name}", timeout=6) as resp:
                data = resp.read()

            if enhance and data:
                try:
                    proc = subprocess.Popen(
                        ["ffmpeg", "-v", "error", "-i", "-", "-vf", "cas=0.50", "-q:v", "2", "-f", "image2", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    enhanced_data, _ = proc.communicate(input=data, timeout=3)
                    if proc.returncode == 0 and enhanced_data:
                        data = enhanced_data
                except Exception as ex:
                    print(f"[Snapshot Enhance] Fallback to raw frame: {ex}", file=sys.stderr)

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, f"Failed to fetch snapshot from go2rtc: {e}")

    def end_headers(self):
        if self.path.endswith(".html") or self.path.endswith(".js") or self.path == "/" or ".js?" in self.path:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.end_headers()
        self.wfile.write(data)

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    threading.Thread(target=_stream_watchdog_loop, daemon=True).start()
    server = ThreadedTCPServer(("", PORT), CCTVHandler)
    print(f"CCTV Dashboard Server listening on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
