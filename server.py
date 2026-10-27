#!/usr/bin/env python3
import http.server
import socketserver
import json
import socket
import hashlib
import time
import os
import urllib.request
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES

CAMERA_IP = "192.168.1.11"
CAMERA_PORT = 54321
TOKEN_HEX = "5a757051646b6175546d4a524d38726c"
TOKEN = bytes.fromhex(TOKEN_HEX)
PORT = 8088
GO2RTC_API = "http://127.0.0.1:1984"

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
        super().__init__(*args, directory="/root/cctv_dashboard/public", **kwargs)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.handle_api_status()
        elif parsed.path == "/api/ping":
            self.handle_api_ping()
        elif parsed.path == "/api/auth/status":
            self.handle_auth_status()
        elif parsed.path.startswith("/api/snapshot/"):
            self.handle_snapshot(parsed.path)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except:
            data = {}

        if parsed.path == "/api/control/light":
            # White light floodlight: siid 16, piid 1
            state = bool(data.get("state", False))
            res = send_miio_rpc("set_properties", [{"did": "1178517372", "siid": 16, "piid": 1, "value": state}])
            self.send_json({"success": True, "result": res, "state": state})

        elif parsed.path == "/api/control/power":
            # Camera lens power: siid 2, piid 1
            state = bool(data.get("state", True))
            res = send_miio_rpc("set_properties", [{"did": "1178517372", "siid": 2, "piid": 1, "value": state}])
            self.send_json({"success": True, "result": res, "state": state})

        elif parsed.path == "/api/control/nightshot":
            # Night vision mode: siid 2, piid 3 (0: Off, 1: On, 2: Auto)
            val = int(data.get("value", 2))
            res = send_miio_rpc("set_properties", [{"did": "1178517372", "siid": 2, "piid": 3, "value": val}])
            self.send_json({"success": True, "result": res, "value": val})

        elif parsed.path == "/api/action/p2p":
            # Start P2P stream: siid 9, aiid 1
            res = send_miio_rpc("action", {"did": "1178517372", "siid": 9, "aiid": 1, "in": []})
            self.send_json({"success": True, "result": res})

        elif parsed.path == "/api/action/reboot":
            # Reboot camera: siid 2, aiid 2
            res = send_miio_rpc("action", {"did": "1178517372", "siid": 2, "aiid": 2, "in": []})
            self.send_json({"success": True, "result": res})

        elif parsed.path == "/api/auth/login":
            # Initiate Xiaomi login via go2rtc
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
            # Verify Xiaomi OTP via go2rtc
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

        elif parsed.path == "/api/auth/reload_streams":
            # Reload streams in go2rtc
            try:
                with urllib.request.urlopen(f"{GO2RTC_API}/api/streams", timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.send_json({"success": True, "streams": data})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_status(self):
        try:
            info = send_miio_rpc("miIO.info", [])
            props = send_miio_rpc("get_properties", [
                {"did": "1178517372", "siid": 2, "piid": 1},   # Power
                {"did": "1178517372", "siid": 16, "piid": 1},  # Light
                {"did": "1178517372", "siid": 2, "piid": 3},   # Nightshot
                {"did": "1178517372", "siid": 9, "piid": 1},   # Video Codec
                {"did": "1178517372", "siid": 9, "piid": 9},   # Resolution
            ])
            self.send_json({
                "online": True,
                "info": info.get("result", {}),
                "properties": props.get("result", []),
                "timestamp": time.time()
            })
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
                "user_id": "1778813257",
                "email": "tadincahrancamaya@gmail.com",
                "region": "sg",
                "did": "1178517372",
                "model": "chuangmi.camera.075ae1",
                "streams": {
                    "kiri": "cctv_garasi_kiri",
                    "kanan": "cctv_garasi_kanan"
                }
            })
        except Exception as e:
            self.send_json({"authenticated": False, "error": str(e)})

    def handle_snapshot(self, path):
        stream_name = "cctv_garasi_kanan" if "right" in path or "kanan" in path else "cctv_garasi_kiri"
        try:
            with urllib.request.urlopen(f"{GO2RTC_API}/api/frame.jpeg?src={stream_name}", timeout=6) as resp:
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_error(502, f"Failed to fetch snapshot from go2rtc: {e}")

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    os.makedirs("/root/cctv_dashboard/public", exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", PORT), CCTVHandler)
    print(f"CCTV Dashboard Server listening on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
