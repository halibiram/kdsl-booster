import pytest
import json
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock analysis data
ZTE_DNS_HOSTNAME = "dslam-c320-london.zte.isp.com"
HUAWEI_TR069_ANALYSIS = {"manufacturer": "Huawei Technologies Co., Ltd."}
HUAWEI_GHS_ANALYSIS = {
    "vendor_id": "HWTC",
    "vsi": b"MA5608T",
    "cl_message_payload": b"\x02\x91\x0f\x00\xb5HWTCMA5608T\x00\x00",
    "handshake_duration": 190.0  # Specific value to only match Huawei
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
            "dns": {"vendor_patterns": ["huawei"]},
            "tr069": {"manufacturer_patterns": ["Huawei"]},
            "timing": {"handshake_duration_ms": {"min": 180, "max": 220}},
            "ghs": {"signatures": [{"vendor_id": "HWTC", "vsi_patterns": ["MA5608T"]}]}
        },
        "nokia_alcatel": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.637"},
            "timing": {"handshake_duration_ms": {"min": 200, "max": 250}},
            "ghs": {"signatures": [{"vendor_id": "ALCL"}]}
        },
        "zte": {
            "timing": {"handshake_duration_ms": {"min": 150, "max": 180}}
        }
    }
    p = tmp_path / "signatures.json"
    p.write_text(json.dumps(sig_data))
    return str(p)


@pytest.fixture
def dslam_detector(mock_ssh_interface, signature_file):
    """Provides a UniversalDSLAMDetector instance with mocks for all analyzers."""
    with patch('src.dslam_detector.GHSHandshakeAnalyzer') as mock_ghs_class, \
         patch('src.dslam_detector.DHCPAnalyzer') as mock_dhcp_class, \
         patch('src.dslam_detector.DNSAnalyzer') as mock_dns_class, \
         patch('src.dslam_detector.TR069Analyzer') as mock_tr069_class:

        detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=signature_file)
        detector.ghs_analyzer = mock_ghs_class.return_value
        detector.dhcp_analyzer = mock_dhcp_class.return_value
        detector.dns_analyzer = mock_dns_class.return_value
        detector.tr069_analyzer = mock_tr069_class.return_value
        yield detector


def test_calculate_timing_confidence_success(dslam_detector):
    """Tests that a duration within a vendor's range returns a correct match."""
    # This duration (210ms) is in Huawei's and Nokia's range in the test data
    analysis = {"handshake_duration": 210.5}
    results = dslam_detector._calculate_timing_confidence(analysis)

    assert len(results) == 2
    vendors = {r['vendor'] for r in results}
    assert 'huawei' in vendors
    assert 'nokia_alcatel' in vendors
    assert results[0]['confidence'] == dslam_detector.TIMING_MATCH_SCORE
    assert results[0]['method'] == 'timing'

def test_calculate_timing_confidence_no_match(dslam_detector):
    """Tests that a duration outside all ranges returns no match."""
    analysis = {"handshake_duration": 500.0}
    results = dslam_detector._calculate_timing_confidence(analysis)
    assert len(results) == 0

def test_calculate_timing_confidence_no_duration(dslam_detector):
    """Tests that no match is returned if duration is missing from analysis."""
    analysis = {"vendor_id": "HWTC"} # No handshake_duration key
    results = dslam_detector._calculate_timing_confidence(analysis)
    assert len(results) == 0

def test_detect_via_g_hs_includes_timing(dslam_detector):
    """
    Tests that the main G.hs detection method returns both signature
    and timing results from a single analysis.
    """
    dslam_detector.ghs_analyzer.analyze_capture.return_value = HUAWEI_GHS_ANALYSIS
    results = dslam_detector._detect_via_g_hs()

    # Expect 2 results: one for GHS signature, one for timing
    assert len(results) == 2
    methods = {r['method'] for r in results}
    assert 'g_hs' in methods
    assert 'timing' in methods

    # Check that the GHS result has a high confidence score
    ghs_result = next(r for r in results if r['method'] == 'g_hs')
    assert ghs_result['confidence'] > dslam_detector.TIMING_MATCH_SCORE

def test_identify_vendor_all_methods(dslam_detector):
    """
    Tests the full identify_vendor flow where multiple methods return results,
    and the highest confidence one is chosen.
    """
    # G.hs returns a strong match for Huawei
    dslam_detector.ghs_analyzer.analyze_capture.return_value = HUAWEI_GHS_ANALYSIS
    # SNMP fails
    dslam_detector.ssh.execute_command.return_value = ("", "Timeout")
    # DNS returns a weaker match for ZTE
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = ZTE_DNS_HOSTNAME
    # DHCP fails
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = None
    # TR-069 fails
    dslam_detector.tr069_analyzer.capture_and_analyze.return_value = None

    # The G.hs signature match for Huawei should be the highest confidence
    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['vendor'] == 'huawei'
    assert result['method'] == 'g_hs'
    assert result['confidence'] == 85 # 70 (ID) + 15 (VSI)