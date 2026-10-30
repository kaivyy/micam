import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server
from xiaomi_wizard import wizard_session


def test_wizard_check_configured_false_when_empty():
    with patch.dict(os.environ, {"CCTV_CAMERA_IP": "", "CCTV_DID": "", "CCTV_TOKEN_HEX": ""}):
        status = server.get_wizard_configuration_status()
        assert status["configured"] is False


def test_wizard_check_configured_true_when_valid():
    with patch.dict(os.environ, {
        "CCTV_CAMERA_IP": "192.168.1.11",
        "CCTV_DID": "1178517372",
        "CCTV_TOKEN_HEX": "5a757051646b6175546d4a524d38726c",
        "CCTV_LENS_MODE": "dual"
    }):
        status = server.get_wizard_configuration_status()
        assert status["configured"] is True
        assert status["camera"]["ip"] == "192.168.1.11"
        assert status["camera"]["lens_type"] == "dual"


def test_wizard_start_api():
    with patch.object(wizard_session, "start_qr_session", return_value={
        "success": True,
        "qr_url": "https://account.xiaomi.com/qr",
        "login_url": "https://account.xiaomi.com/login",
        "timeout": 120
    }):
        res = wizard_session.start_qr_session()
        assert res["success"] is True
        assert res["qr_url"] == "https://account.xiaomi.com/qr"
