import pytest
import json
import logging
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock findings from the various analyzers
HUAWEI_GHS_FINDING = {"vendor": "huawei", "certainty": 95, "method": "g_hs", "raw_data": "VSI: MA5608T"}
ZTE_GHS_FINDING = {"vendor": "zte", "certainty": 90, "method": "g_hs", "raw_data": "VSI: ZXA10"}
NOKIA_SNMP_FINDING = {"vendor": "nokia_alcatel", "certainty": 100, "method": "snmp", "raw_data": "1.3.6.1.4.1.637.1.2.3"}
HUAWEI_TIMING_FINDING = {"vendor": "huawei", "certainty": 100, "method": "timing", "raw_data": "190.00ms"}
ZTE_DNS_FINDING = {"vendor": "zte", "certainty": 100, "method": "dns", "raw_data": "dslam-c320-london.zte.isp.com"}


@pytest.fixture
def mock_ssh_interface():
    """Provides a mock EntwareSSHInterface for testing."""
    return MagicMock()

@pytest.fixture
def signature_file(tmp_path):
    """Creates a temporary, minimal signature JSON file for testing."""
    # The contents don't need to be extensive, but the file cannot be empty
    # for the main identify_vendor method to proceed.
    sig_data = {
        "huawei": { "snmp": {"sysObjectID": "1.3.6.1.4.1.2011"} },
        "nokia_alcatel": { "snmp": {"sysObjectID": "1.3.6.1.4.1.637"} },
        "zte": { "dns": {"vendor_patterns": ["zte"]} }
    }
    p = tmp_path / "signatures.json"
    p.write_text(json.dumps(sig_data))
    return str(p)

@pytest.fixture
def dslam_detector(mock_ssh_interface, signature_file):
    """Provides a UniversalDSLAMDetector instance with mocked detection methods."""
    with patch.object(UniversalDSLAMDetector, '_detect_via_g_hs', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_snmp', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_dhcp', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_dns', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_tr069', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_timing', return_value=[]):

        detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=signature_file)
        yield detector

def test_identify_vendor_snmp_wins(dslam_detector):
    """
    Tests a clear win for a vendor based on a high-weight method (SNMP).
    """
    dslam_detector._detect_via_snmp.return_value = [NOKIA_SNMP_FINDING]
    dslam_detector._detect_via_dns.return_value = [ZTE_DNS_FINDING] # Lower weight method

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['primary_vendor'] == 'nokia_alcatel'
    # Expected score: 100% certainty * 30% weight = 30.0
    assert result['overall_confidence'] == 30.0
    assert len(result['contributing_methods']) == 1
    assert result['contributing_methods'][0]['method'] == 'snmp'

def test_identify_vendor_aggregation_of_evidence(dslam_detector):
    """
    Tests that evidence from multiple methods is correctly aggregated for one vendor.
    """
    dslam_detector._detect_via_g_hs.return_value = [HUAWEI_GHS_FINDING]
    dslam_detector._detect_via_timing.return_value = [HUAWEI_TIMING_FINDING]

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['primary_vendor'] == 'huawei'
    # Expected score:
    # G.hs: 95% certainty * 35% weight = 33.25
    # Timing: 100% certainty * 1% weight = 1.0
    # Total = 34.25
    assert result['overall_confidence'] == 34.25
    assert len(result['contributing_methods']) == 2

def test_identify_vendor_conflict_resolution(dslam_detector, caplog):
    """
    Tests that a warning is logged when two vendors have high, close scores.
    """
    dslam_detector._detect_via_g_hs.return_value = [HUAWEI_GHS_FINDING] # Score: 0.95 * 35 = 33.25
    dslam_detector._detect_via_snmp.return_value = [NOKIA_SNMP_FINDING] # Score: 1.00 * 30 = 30.0

    with caplog.at_level(logging.WARNING):
        result = dslam_detector.identify_vendor()
        assert "Conflict detected" in caplog.text
        assert "Top: huawei (33.25%)" in caplog.text
        assert "Second: nokia_alcatel (30.00%)" in caplog.text

    # The top result should still be returned
    assert result is not None
    assert result['primary_vendor'] == 'huawei'

def test_identify_vendor_no_findings(dslam_detector):
    """
    Tests that None is returned when no detection methods yield any findings.
    """
    # All methods are mocked to return [] by default in the fixture
    result = dslam_detector.identify_vendor()
    assert result is None

def test_final_output_format(dslam_detector):
    """
    Tests that the returned dictionary has the correct structure.
    """
    dslam_detector._detect_via_g_hs.return_value = [HUAWEI_GHS_FINDING]

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert 'primary_vendor' in result
    assert 'overall_confidence' in result
    assert 'contributing_methods' in result
    assert isinstance(result['contributing_methods'], list)
    assert len(result['contributing_methods']) == 1
    assert result['contributing_methods'][0]['method'] == 'g_hs'
    assert 'raw_data' in result['contributing_methods'][0]