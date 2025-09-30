import pytest
import json
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock analysis data from GHSHandshakeAnalyzer, with corrected payloads
HUAWEI_ANALYSIS = {
    "vendor_id": "HWTC",
    "vsi": b"MA5608T\x00\x00",
    "cl_message_payload": b"\x02\x91\x0f\x00\xb5HWTCMA5608T\x00\x00"
}
ALCATEL_ANALYSIS = {
    "vendor_id": "ALCL",
    "vsi": b"7330ISAM\x01\x02",
    "cl_message_payload": b"\x02\x91\x10\x00\xb5ALCL7330ISAM\x01\x02"
}
PARTIAL_MATCH_ANALYSIS = { # Matches Broadcom by VSI but not Vendor ID
    "vendor_id": "ZZZZ",
    "vsi": b"BCM_Chipset_V1",
    "cl_message_payload": b"\x02\x91\x0a\x00\xb5ZZZZBCM_V1"
}
NO_MATCH_ANALYSIS = {
    "vendor_id": "XXXX",
    "vsi": b"UnknownDevice",
    "cl_message_payload": b"\x02\x91\x0a\x00\xb5XXXXUnknown"
}


@pytest.fixture
def mock_ssh_interface():
    """Provides a mock EntwareSSHInterface for testing."""
    ssh_mock = MagicMock()
    ssh_mock.execute_command.return_value = ("", "Command failed")
    return ssh_mock


@pytest.fixture
def signature_file(tmp_path):
    """Creates a temporary signature JSON file for isolated testing."""
    sig_data = {
        "huawei": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.2011"},
            "ghs": {"signatures": [{
                "description": "MA5608T", "vendor_id": "HWTC",
                "vsi_patterns": ["MA5608T", "MA5600"], "cl_payload_pattern": "02910f"
            }]}
        },
        "nokia_alcatel": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.637"},
            "ghs": {"signatures": [{
                "description": "7330 ISAM", "vendor_id": "ALCL",
                "vsi_patterns": ["ISAM", "7330"], "cl_payload_pattern": "029110"
            }]}
        },
        "broadcom": {
            "ghs": {"signatures": [{
                "description": "Generic BCM", "vendor_id": "BDCM",
                "vsi_patterns": ["BCM"], "cl_payload_pattern": ""
            }]}
        }
    }
    p = tmp_path / "signatures.json"
    p.write_text(json.dumps(sig_data))
    return str(p)


@pytest.fixture
def dslam_detector(mock_ssh_interface, signature_file):
    """Provides a UniversalDSLAMDetector instance with mocks."""
    with patch('src.dslam_detector.GHSHandshakeAnalyzer') as mock_analyzer_class:
        detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=signature_file)
        detector.ghs_analyzer = mock_analyzer_class.return_value
        yield detector


def test_detect_via_snmp_success(dslam_detector, mock_ssh_interface):
    """Tests successful vendor identification using the real SNMP method."""
    # Mock the SSH command to return a realistic snmpget response for Huawei
    huawei_oid = "1.3.6.1.4.1.2011.2.82.8"
    mock_ssh_interface.execute_command.return_value = (huawei_oid, "")

    results = dslam_detector._detect_via_snmp()

    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == dslam_detector.SNMP_MATCH_SCORE
    assert result['method'] == 'snmp'
    assert huawei_oid in result['description']
    mock_ssh_interface.execute_command.assert_called_once_with(
        "snmpget -v2c -c public -t 1 -O vq 192.168.1.1 1.3.6.1.2.1.1.2.0"
    )

def test_detect_via_snmp_no_match(dslam_detector, mock_ssh_interface):
    """Tests SNMP detection when the returned OID does not match any signature."""
    unknown_oid = "1.3.6.1.4.1.9999.1.1"
    mock_ssh_interface.execute_command.return_value = (unknown_oid, "")

    results = dslam_detector._detect_via_snmp()

    assert len(results) == 0

def test_detect_via_snmp_command_fails(dslam_detector, mock_ssh_interface):
    """Tests SNMP detection when the snmpget command fails."""
    mock_ssh_interface.execute_command.return_value = ("", "Timeout: No Response from 192.168.1.1")

    results = dslam_detector._detect_via_snmp()

    assert len(results) == 0

def test_calculate_ghs_confidence_full_match(dslam_detector):
    """Tests a high-confidence GHS match."""
    results = dslam_detector._calculate_ghs_confidence(HUAWEI_ANALYSIS)
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == 90

def test_identify_vendor_snmp_is_best_match(dslam_detector, mock_ssh_interface):
    """Tests that the best result is chosen when SNMP has the highest confidence."""
    # G.hs provides a low-confidence match
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = PARTIAL_MATCH_ANALYSIS # Confidence 15

    # SNMP provides a high-confidence match for Nokia
    nokia_oid = "1.3.6.1.4.1.637.1.2.3"
    mock_ssh_interface.execute_command.return_value = (nokia_oid, "")

    result = dslam_detector.identify_vendor(methods=['g_hs', 'snmp'])

    assert result is not None
    assert result['vendor'] == 'nokia_alcatel'
    assert result['confidence'] == dslam_detector.SNMP_MATCH_SCORE

def test_load_signatures_file_not_found(mock_ssh_interface):
    """Tests graceful handling of a missing signature file."""
    detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file="/non/existent/file.json")
    assert detector.signatures == {}
    assert detector.identify_vendor() is None

def test_load_signatures_corrupt_json(tmp_path, mock_ssh_interface):
    """Tests graceful handling of a corrupt signature file."""
    p = tmp_path / "corrupt.json"
    p.write_text("{'not_json': True,}") # Invalid JSON
    detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=str(p))
    assert detector.signatures == {}
    assert detector.identify_vendor() is None