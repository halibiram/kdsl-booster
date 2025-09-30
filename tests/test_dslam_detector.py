import pytest
import json
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock analysis data from GHSHandshakeAnalyzer
HUAWEI_GHS_ANALYSIS = {
    "vendor_id": "HWTC",
    "vsi": b"MA5608T\x00\x00",
    "cl_message_payload": b"\x02\x91\x0f\x00\xb5HWTCMA5608T\x00\x00"
}
# Mock analysis data from DHCPAnalyzer
HUAWEI_DHCP_ANALYSIS = {"circuit_id": b"0a/1b/2c/3d/4e"}
ALCATEL_DHCP_ANALYSIS = {"circuit_id": b"ATM 1:2:3:4"}
UNKNOWN_DHCP_ANALYSIS = {"circuit_id": b"some_unknown_format"}


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
            "dhcp": {"circuit_id_pattern": "^([0-9a-fA-F]{2}/){4}[0-9a-fA-F]{2}$"},
            "ghs": {"signatures": [{"description": "MA5608T", "vendor_id": "HWTC"}]}
        },
        "nokia_alcatel": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.637"},
            "dhcp": {"circuit_id_pattern": "^ATM [0-9]+:[0-9]+:[0-9]+:[0-9]+$"},
            "ghs": {"signatures": [{"description": "7330 ISAM", "vendor_id": "ALCL"}]}
        }
    }
    p = tmp_path / "signatures.json"
    p.write_text(json.dumps(sig_data))
    return str(p)


@pytest.fixture
def dslam_detector(mock_ssh_interface, signature_file):
    """Provides a UniversalDSLAMDetector instance with mocks for all analyzers."""
    with patch('src.dslam_detector.GHSHandshakeAnalyzer') as mock_ghs_class, \
         patch('src.dslam_detector.DHCPAnalyzer') as mock_dhcp_class:

        detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=signature_file)
        detector.ghs_analyzer = mock_ghs_class.return_value
        detector.dhcp_analyzer = mock_dhcp_class.return_value
        yield detector


def test_detect_via_snmp_success(dslam_detector, mock_ssh_interface):
    """Tests successful vendor identification using the SNMP method."""
    huawei_oid = "1.3.6.1.4.1.2011.2.82.8"
    mock_ssh_interface.execute_command.return_value = (huawei_oid, "")

    results = dslam_detector._detect_via_snmp()

    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == dslam_detector.SNMP_MATCH_SCORE

def test_detect_via_dhcp_success(dslam_detector):
    """Tests successful vendor identification using the DHCP method."""
    # Mock the DHCPAnalyzer to return a circuit ID matching the Huawei pattern
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = HUAWEI_DHCP_ANALYSIS

    results = dslam_detector._detect_via_dhcp()

    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == dslam_detector.DHCP_MATCH_SCORE
    assert result['method'] == 'dhcp'
    dslam_detector.dhcp_analyzer.capture_and_analyze.assert_called_once()

def test_detect_via_dhcp_no_match(dslam_detector):
    """Tests DHCP detection when the Circuit ID does not match any pattern."""
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = UNKNOWN_DHCP_ANALYSIS

    results = dslam_detector._detect_via_dhcp()

    assert len(results) == 0

def test_detect_via_dhcp_analysis_fails(dslam_detector):
    """Tests DHCP detection when the analyzer returns None."""
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = None

    results = dslam_detector._detect_via_dhcp()

    assert len(results) == 0

def test_identify_vendor_dhcp_is_best_match(dslam_detector, mock_ssh_interface):
    """Tests that the best result is chosen when DHCP has the highest confidence."""
    # GHS and SNMP fail or have low confidence
    dslam_detector.ghs_analyzer.capture_and_analyze.return_value = None
    mock_ssh_interface.execute_command.return_value = ("", "Timeout") # SNMP fails

    # DHCP provides a high-confidence match for Alcatel
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = ALCATEL_DHCP_ANALYSIS

    result = dslam_detector.identify_vendor(methods=['g_hs', 'snmp', 'dhcp'])

    assert result is not None
    assert result['vendor'] == 'nokia_alcatel'
    assert result['confidence'] == dslam_detector.DHCP_MATCH_SCORE

def test_load_signatures_file_not_found(mock_ssh_interface):
    """Tests graceful handling of a missing signature file."""
    detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file="/non/existent/file.json")
    assert detector.signatures == {}
    assert detector.identify_vendor() is None