import pytest
import json
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock analysis data
ZTE_DNS_HOSTNAME = "dslam-c320-london.zte.isp.com"
HUAWEI_TR069_ANALYSIS = {"manufacturer": "Huawei Technologies Co., Ltd."}
NOKIA_TR069_ANALYSIS = {"manufacturer": "Nokia"}


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
            "dns": {"vendor_patterns": ["huawei"], "model_patterns": ["ma5600"]},
            "tr069": {"manufacturer_patterns": ["Huawei"]}
        },
        "nokia_alcatel": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.637"},
            "dhcp": {"circuit_id_pattern": "^ATM [0-9]+:[0-9]+:[0-9]+:[0-9]+$"},
            "dns": {"vendor_patterns": ["nokia", "alu"], "model_patterns": ["isam"]},
            "tr069": {"manufacturer_patterns": ["Nokia", "Alcatel-Lucent"]}
        },
        "zte": {
            "dns": {"vendor_patterns": ["zte"], "model_patterns": ["c320"]}
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


def test_detect_via_snmp_success(dslam_detector, mock_ssh_interface):
    """Tests successful SNMP vendor identification."""
    huawei_oid = "1.3.6.1.4.1.2011.2.82.8"
    mock_ssh_interface.execute_command.return_value = (huawei_oid, "")
    results = dslam_detector._detect_via_snmp()
    assert len(results) == 1
    assert results[0]['vendor'] == 'huawei'

def test_detect_via_dhcp_success(dslam_detector):
    """Tests successful DHCP vendor identification."""
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = {"circuit_id": b"ATM 1:2:3:4"}
    results = dslam_detector._detect_via_dhcp()
    assert len(results) == 1
    assert results[0]['vendor'] == 'nokia_alcatel'

def test_detect_via_dns_success(dslam_detector):
    """Tests successful DNS vendor identification."""
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = ZTE_DNS_HOSTNAME
    results = dslam_detector._detect_via_dns()
    assert len(results) == 1
    assert results[0]['vendor'] == 'zte'

def test_detect_via_tr069_success(dslam_detector):
    """Tests successful TR-069 vendor identification."""
    dslam_detector.tr069_analyzer.capture_and_analyze.return_value = HUAWEI_TR069_ANALYSIS
    results = dslam_detector._detect_via_tr069()
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == dslam_detector.TR069_MANUFACTURER_SCORE

def test_detect_via_tr069_no_match(dslam_detector):
    """Tests TR-069 detection when the manufacturer does not match."""
    dslam_detector.tr069_analyzer.capture_and_analyze.return_value = {"manufacturer": "UnknownCorp"}
    results = dslam_detector._detect_via_tr069()
    assert len(results) == 0

def test_detect_via_tr069_analysis_fails(dslam_detector):
    """Tests TR-069 detection when the analyzer returns None."""
    dslam_detector.tr069_analyzer.capture_and_analyze.return_value = None
    results = dslam_detector._detect_via_tr069()
    assert len(results) == 0

def test_identify_vendor_tr069_is_best_match(dslam_detector, mock_ssh_interface):
    """Tests that the best result is chosen when TR-069 has the highest confidence."""
    # Mock other methods to fail or have low confidence
    dslam_detector.ghs_analyzer.capture_and_analyze.return_value = None
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = None
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = None
    mock_ssh_interface.execute_command.return_value = ("", "Timeout") # SNMP fails

    # TR-069 provides a high-confidence match
    dslam_detector.tr069_analyzer.capture_and_analyze.return_value = NOKIA_TR069_ANALYSIS

    result = dslam_detector.identify_vendor()

    assert result is not None
    assert result['vendor'] == 'nokia_alcatel'
    assert result['confidence'] == dslam_detector.TR069_MANUFACTURER_SCORE