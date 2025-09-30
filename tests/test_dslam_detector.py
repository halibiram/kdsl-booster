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
    # Default behavior: all commands fail unless overridden in a test
    ssh_mock.execute_command.return_value = ("", "Command failed")
    return ssh_mock


@pytest.fixture
def signature_file(tmp_path):
    """Creates a temporary signature JSON file for isolated testing."""
    sig_data = {
        "huawei": {
            "signatures": [{
                "description": "MA5608T", "vendor_id": "HWTC",
                "vsi_patterns": ["MA5608T", "MA5600"], "cl_payload_pattern": "02910f"
            }]
        },
        "nokia_alcatel": {
            "signatures": [{
                "description": "7330 ISAM", "vendor_id": "ALCL",
                "vsi_patterns": ["ISAM", "7330"], "cl_payload_pattern": "029110"
            }]
        },
        "broadcom": {
            "signatures": [{
                "description": "Generic BCM", "vendor_id": "BDCM",
                "vsi_patterns": ["BCM"], "cl_payload_pattern": ""
            }]
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


def test_calculate_ghs_confidence_full_match(dslam_detector):
    """Tests a high-confidence match from Vendor ID and VSI pattern."""
    results = dslam_detector._calculate_ghs_confidence(HUAWEI_ANALYSIS)
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    # VENDOR_ID_MATCH_SCORE (70) + VSI_PATTERN_MATCH_SCORE (15) + PAYLOAD_MATCH_SCORE (5)
    assert result['confidence'] == 90
    assert result['description'] == 'MA5608T'

def test_calculate_ghs_confidence_vendor_id_only(dslam_detector):
    """Tests a medium-confidence match from only the Vendor ID."""
    analysis = HUAWEI_ANALYSIS.copy()
    analysis['vsi'] = b'UnknownModel'
    results = dslam_detector._calculate_ghs_confidence(analysis)
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    # VENDOR_ID_MATCH_SCORE (70) + PAYLOAD_MATCH_SCORE (5)
    assert result['confidence'] == 75

def test_calculate_ghs_confidence_vsi_only(dslam_detector):
    """Tests a low-confidence match from only a VSI pattern."""
    results = dslam_detector._calculate_ghs_confidence(PARTIAL_MATCH_ANALYSIS)
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'broadcom'
    # VSI_PATTERN_MATCH_SCORE (15)
    assert result['confidence'] == 15

def test_calculate_ghs_confidence_no_match(dslam_detector):
    """Tests that no results are returned when no part of the signature matches."""
    results = dslam_detector._calculate_ghs_confidence(NO_MATCH_ANALYSIS)
    assert len(results) == 0

def test_identify_vendor_g_hs_is_best_match(dslam_detector):
    """Tests that the best result is chosen when G.hs has the highest confidence."""
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = ALCATEL_ANALYSIS

    # Mock SNMP and DHCP to return lower-confidence results
    dslam_detector._detect_via_snmp = MagicMock(return_value=[])
    dslam_detector._detect_via_dhcp = MagicMock(return_value=[])

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['vendor'] == 'nokia_alcatel'
    # Score is 70 (ID) + 15 (ISAM) + 15 (7330) + 5 (Payload) = 105, capped at 100
    assert result['confidence'] == 100

def test_identify_vendor_below_threshold(dslam_detector):
    """Tests that no result is returned if the best match is below the confidence threshold."""
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = PARTIAL_MATCH_ANALYSIS # Confidence 15

    # Make other methods fail
    dslam_detector._detect_via_snmp = MagicMock(return_value=[])
    dslam_detector._detect_via_dhcp = MagicMock(return_value=[])

    result = dslam_detector.identify_vendor()
    assert result is None

def test_identify_vendor_snmp_is_best_match(dslam_detector, mock_ssh_interface):
    """Tests that the best result is chosen when SNMP has the highest confidence."""
    # G.hs provides a low-confidence match
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = PARTIAL_MATCH_ANALYSIS # Confidence 15

    # SNMP provides a high-confidence match
    mock_ssh_interface.execute_command.return_value = ("enterprises.2011", "") # Mock for Huawei

    # To isolate, we'll replace the detector's method with a standard mock
    dslam_detector._detect_via_snmp = MagicMock(return_value=[{
        "vendor": "huawei", "confidence": 95, "description": "SNMP sysObjectID match", "method": "snmp"
    }])
    dslam_detector._detect_via_dhcp = MagicMock(return_value=[])

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == 95

def test_load_signatures_file_not_found():
    """Tests that the detector handles a missing signature file gracefully."""
    detector = UniversalDSLAMDetector(MagicMock(), signature_file="/non/existent/file.json")
    assert detector.signatures == {}
    result = detector.identify_vendor()
    assert result is None

def test_load_signatures_corrupt_json(tmp_path):
    """Tests that the detector handles a corrupt signature file."""
    p = tmp_path / "corrupt.json"
    p.write_text("{'not_json': True,}") # Invalid JSON
    detector = UniversalDSLAMDetector(MagicMock(), signature_file=str(p))
    assert detector.signatures == {}
    result = detector.identify_vendor()
    assert result is None