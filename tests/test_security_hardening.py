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

    # Also verify apply_camera_config rejects injection and leaves files untouched
    with tempfile.TemporaryDirectory() as tmpdir:
        session = XiaomiWizardSession()
        ok = session.apply_camera_config({**base_cam, "ip": "192.168.1.1\n  pwn: exec:id"}, base_dir=tmpdir)
        assert ok is False
        assert not os.path.exists(os.path.join(tmpdir, "go2rtc.yaml"))


def test_go2rtc_yaml_includes_allow_paths_and_exec_restriction():
    yaml_text = generate_go2rtc_yaml({
        "ip": "192.168.1.55",
        "did": "987654321",
        "model": "chuangmi.camera.075ae1",
        "lens_type": "dual",
        "region": "sg",
        "user_id": "12345678",
        "pass_token": "V1:mockpasstokendata==",
    })
    assert "allow_paths:" in yaml_text
    assert "- /api/ws" in yaml_text
    assert "/api/config" not in yaml_text
    assert "/api/exit" not in yaml_text
    assert "exec:\n  allow_paths:\n    - ffmpeg" in yaml_text


def test_live_go2rtc_blocks_config_leak_and_dynamic_stream_injection():
    # 1. GET /api/config must be blocked (404 or 403)
    req_cfg = urllib.request.Request("http://127.0.0.1:1984/api/config", method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_cfg, timeout=3)
    assert exc_info.value.code in (403, 404)

    # 2. PUT /api/streams?name=pwn&src=exec:id must be blocked (403 Forbidden)
    req_put = urllib.request.Request(
        "http://127.0.0.1:1984/api/streams?name=pwn&src=exec:id",
        data=b"",
        method="PUT",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_put, timeout=3)
    assert exc_info.value.code == 403

    # 3. DELETE /api/streams?src=cctv_lensa_kiri must be blocked (403 Forbidden)
    req_del = urllib.request.Request(
        "http://127.0.0.1:1984/api/streams?src=cctv_lensa_kiri",
        method="DELETE",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_del, timeout=3)
    assert exc_info.value.code == 403

    # 4. POST /api/restart from non-loopback LAN IP must be blocked (403 Forbidden)
    req_lan_restart = urllib.request.Request(
        "http://192.168.1.44:1984/api/restart",
        data=b"",
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_lan_restart, timeout=3)
    assert exc_info.value.code == 403


def test_server_redacts_tokens_and_blocks_csrf_and_unauth_wizard_save():
    # 1. /api/status must not expose MIIO 32-char hex token
    with urllib.request.urlopen("http://127.0.0.1:8088/api/status", timeout=5) as resp:
        status_data = json.loads(resp.read().decode("utf-8"))
        info = status_data.get("info") or {}
        assert "token" not in info

    # 2. /api/wizard/devices must not expose MIIO 32-char hex token
    with urllib.request.urlopen("http://127.0.0.1:8088/api/wizard/devices", timeout=5) as resp:
        dev_data = json.loads(resp.read().decode("utf-8"))
        for cam in dev_data.get("cameras", []):
            assert "token" not in cam

    # 3. Unauthenticated arbitrary DID overwrite on /api/wizard/save must return 403
    bad_save = urllib.request.Request(
        "http://127.0.0.1:8088/api/wizard/save",
        data=json.dumps({"did": "999999999", "ip": "192.168.1.11\n  pwn: exec:id"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(bad_save, timeout=5)
    assert exc_info.value.code in (400, 403)

    # 4. Cross-origin POST from external website must return 403 Forbidden
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
