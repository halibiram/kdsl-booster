import pytest
import json
import logging
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector
from src.log_manager import LogManager

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
    sig_data = {
        "huawei": {"snmp": {"sysObjectID": "1.3.6.1.4.1.2011"}},
        "nokia_alcatel": {"snmp": {"sysObjectID": "1.3.6.1.4.1.637"}},
        "zte": {"dns": {"vendor_patterns": ["zte"]}}
    }
    p = tmp_path / "signatures.json"
    p.write_text(json.dumps(sig_data))
    return str(p)

@pytest.fixture
def dslam_detector(mock_ssh_interface, signature_file):
    """Provides a UniversalDSLAMDetector instance with mocked detection methods."""
    # Mock the DatabaseManager to avoid file I/O in unit tests
    mock_db_manager = MagicMock()
    mock_db_manager.get_all_signatures.return_value = {} # Return empty sigs by default

    log_manager = LogManager(secure_logging_enabled=False)
    with patch.object(UniversalDSLAMDetector, '_detect_via_g_hs', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_snmp', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_dhcp', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_dns', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_tr069', return_value=[]), \
         patch.object(UniversalDSLAMDetector, '_detect_via_timing', return_value=[]):

        detector = UniversalDSLAMDetector(
            target_ip="127.0.0.1",
            community_string="public",
            db_manager=mock_db_manager,
            ssh_interface=mock_ssh_interface,
            log_manager=log_manager
        )

        # Load real signatures for the test's purpose and set them on the instance
        with open(signature_file, 'r') as f:
            sigs = json.load(f)
        detector.signatures = sigs

        yield detector

def test_identify_vendor_snmp_wins(dslam_detector):
    """Tests a clear win for a vendor based on a high-weight method (SNMP)."""
    dslam_detector._detect_via_snmp.return_value = [NOKIA_SNMP_FINDING]
    dslam_detector._detect_via_dns.return_value = [ZTE_DNS_FINDING]
    result = dslam_detector.identify_vendor()
    assert result['primary_vendor'] == 'nokia_alcatel'
    assert result['overall_confidence'] == 30.0

def test_identify_vendor_aggregation_of_evidence(dslam_detector):
    """Tests that evidence from multiple methods is correctly aggregated."""
    dslam_detector._detect_via_g_hs.return_value = [HUAWEI_GHS_FINDING]
    dslam_detector._detect_via_timing.return_value = [HUAWEI_TIMING_FINDING]
    result = dslam_detector.identify_vendor()
    assert result['primary_vendor'] == 'huawei'
    assert result['overall_confidence'] == pytest.approx(34.25) # (0.95 * 35) + (1.0 * 1)
    assert len(result['contributing_methods']) == 2

def test_identify_vendor_conflict_resolution(dslam_detector, caplog):
    """Tests that a detailed warning is logged when two vendors have high, close scores."""
    dslam_detector._detect_via_g_hs.return_value = [HUAWEI_GHS_FINDING] # Score: 33.25
    dslam_detector._detect_via_snmp.return_value = [NOKIA_SNMP_FINDING] # Score: 30.0
    with caplog.at_level(logging.WARNING):
        result = dslam_detector.identify_vendor()
        assert "Event: conflict_detected" in caplog.text
        assert "'top_vendor': 'huawei'" in caplog.text
        assert "'second_vendor': 'nokia_alcatel'" in caplog.text
    assert result['primary_vendor'] == 'huawei'

def test_identify_vendor_below_final_threshold(dslam_detector, caplog):
    """Tests that no result is returned if the best score is below the final threshold."""
    # Timing is the only method, with a low weight of 1
    dslam_detector._detect_via_timing.return_value = [HUAWEI_TIMING_FINDING] # Score: 1.0 * 1 = 1.0
    with caplog.at_level(logging.WARNING):
        result = dslam_detector.identify_vendor()
        assert result is None
        assert "Event: identify_vendor_failed" in caplog.text
        assert "'reason': 'Best match did not meet confidence threshold'" in caplog.text

def test_identify_vendor_no_findings(dslam_detector):
    """Tests that None is returned when no methods yield findings."""
    result = dslam_detector.identify_vendor()
    assert result is None

def test_final_output_format(dslam_detector):
    """Tests that the returned dictionary has the correct, detailed structure."""
    dslam_detector._detect_via_snmp.return_value = [NOKIA_SNMP_FINDING]
    dslam_detector._detect_via_dns.return_value = [ZTE_DNS_FINDING]

    result = dslam_detector.identify_vendor()

    assert 'primary_vendor' in result
    assert 'overall_confidence' in result
    assert 'contributing_methods' in result
    assert 'all_results' in result
    assert isinstance(result['contributing_methods'], list)
    assert isinstance(result['all_results'], dict)
    assert result['all_results']['nokia_alcatel'] == 30.0
    assert result['all_results']['zte'] == 10.0