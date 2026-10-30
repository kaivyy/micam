import os
import json
import time
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Import the module to be implemented
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from xiaomi_wizard import XiaomiWizardSession, detect_lens_type, generate_env_content, generate_go2rtc_yaml


def test_detect_lens_type():
    # Dual lens models
    assert detect_lens_type("chuangmi.camera.075ae1") == "dual"
    assert detect_lens_type("chuangmi.camera.075a") == "dual"
    assert detect_lens_type("xiaomi.camera.cw700dual") == "dual"

    # Single lens models
    assert detect_lens_type("chuangmi.camera.ipc029") == "single"
    assert detect_lens_type("chuangmi.camera.069a01") == "single"
    assert detect_lens_type("mibt.camera.c300") == "single"
    assert detect_lens_type("") == "single"


def test_generate_env_content():
    camera_data = {
        "ip": "192.168.1.55",
        "port": 54321,
        "token": "abcdef0123456789abcdef0123456789",
        "did": "987654321",
        "name": "CCTV Halaman Depan",
        "model": "chuangmi.camera.075ae1",
        "lens_type": "dual",
        "region": "sg",
        "user_id": "12345678"
    }
    content = generate_env_content(camera_data)
    assert "CCTV_CAMERA_IP=192.168.1.55" in content
    assert "CCTV_TOKEN_HEX=abcdef0123456789abcdef0123456789" in content
    assert "CCTV_DID=987654321" in content
    assert "CCTV_LENS_MODE=dual" in content
    assert "XIAOMI_USER_ID=12345678" in content
    assert "XIAOMI_REGION=sg" in content


def test_generate_go2rtc_yaml_dual_lens():
    camera_data = {
        "ip": "192.168.1.55",
        "did": "987654321",
        "model": "chuangmi.camera.075ae1",
        "lens_type": "dual",
        "region": "sg",
        "user_id": "12345678",
        "pass_token": "V1:mockpasstokendata=="
    }
    yaml_text = generate_go2rtc_yaml(camera_data)
    assert 'xiaomi:\n  "12345678": V1:mockpasstokendata==' in yaml_text or '"12345678": V1:mockpasstokendata==' in yaml_text
    assert "cctv_lensa_kiri:" in yaml_text
    assert "cctv_lensa_kanan:" in yaml_text
    assert "channel=2" in yaml_text
    assert "192.168.1.55" in yaml_text
    assert "did=987654321" in yaml_text


def test_generate_go2rtc_yaml_single_lens():
    camera_data = {
        "ip": "192.168.1.70",
        "did": "11223344",
        "model": "chuangmi.camera.ipc029",
        "lens_type": "single",
        "region": "cn",
        "user_id": "998877",
        "pass_token": "V1:mocktoken2=="
    }
    yaml_text = generate_go2rtc_yaml(camera_data)
    assert "cctv_lensa_kiri:" in yaml_text
    # Single lens should not define cctv_lensa_kanan stream
    assert "cctv_lensa_kanan:" not in yaml_text
    assert "channel=2" not in yaml_text
    assert "192.168.1.70" in yaml_text


def test_session_start_qr_mock():
    session = XiaomiWizardSession()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({
        "qr": "https://account.xiaomi.com/qr.png?ticket=123",
        "loginUrl": "https://account.xiaomi.com/longPolling/login?ticket=123",
        "lp": "https://account.xiaomi.com/longPolling/token?ticket=123",
        "timeout": 120
    })

    with patch.object(session._session, "get", return_value=mock_resp):
        res = session.start_qr_session()
        assert res["success"] is True
        assert res["qr_url"] == "https://account.xiaomi.com/qr.png?ticket=123"
        assert res["login_url"] == "https://account.xiaomi.com/longPolling/login?ticket=123"
        assert session.state == "waiting"


def test_session_poll_qr_authorized_mock():
    session = XiaomiWizardSession()
    session.long_polling_url = "https://account.xiaomi.com/lp"
    session.created_at = time.time()
    session.state = "waiting"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({
        "userId": "1778813257",
        "ssecurity": "mocksecurity==",
        "passToken": "V1:mockpass==",
        "location": "https://sts.api.io.mi.com/sts?ticket=xyz"
    })

    mock_loc_resp = MagicMock()
    mock_loc_resp.status_code = 200
    mock_loc_resp.cookies = {"serviceToken": "mockservicetoken123"}

    def side_effect(url, **kwargs):
        if url == session.long_polling_url:
            return mock_resp
        return mock_loc_resp

    with patch.object(session._session, "get", side_effect=side_effect):
        status = session.poll_qr_status(timeout=1)
        assert status["state"] == "authorized"
        assert session.user_id == "1778813257"
        assert session.pass_token == "V1:mockpass=="
        assert session.service_token == "mockservicetoken123"


def test_atomic_config_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        yaml_file = os.path.join(tmpdir, "go2rtc.yaml")

        with open(env_file, "w") as f:
            f.write("OLD_ENV=1\n")
        with open(yaml_file, "w") as f:
            f.write("old_yaml: true\n")

        session = XiaomiWizardSession()
        session.user_id = "123"
        session.pass_token = "V1:test=="

        camera = {
            "ip": "192.168.1.99",
            "token": "0" * 32,
            "did": "555",
            "name": "TestCam",
            "model": "chuangmi.camera.075ae1",
            "lens_type": "dual",
            "region": "sg"
        }

        ok = session.apply_camera_config(camera, base_dir=tmpdir)
        assert ok is True

        # Verify backups exist
        assert os.path.exists(env_file + ".bak")
        assert os.path.exists(yaml_file + ".bak")

        # Verify new files contain generated values
        with open(env_file, "r") as f:
            content = f.read()
            assert "CCTV_CAMERA_IP=192.168.1.99" in content
            assert "CCTV_LENS_MODE=dual" in content

        with open(yaml_file, "r") as f:
            content = f.read()
            assert "cctv_lensa_kiri:" in content
            assert "cctv_lensa_kanan:" in content
