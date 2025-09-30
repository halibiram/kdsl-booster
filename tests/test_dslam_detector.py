import pytest
import json
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector

# Mock analysis data
HUAWEI_DHCP_ANALYSIS = {"circuit_id": b"0a/1b/2c/3d/4e"}
ALCATEL_DHCP_ANALYSIS = {"circuit_id": b"ATM 1:2:3:4"}
ZTE_DNS_HOSTNAME = "dslam-c320-london.zte.isp.com"
HUAWEI_DNS_HOSTNAME = "bras-huawei-manchester.isp.com"


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
            "dns": {"vendor_patterns": ["huawei"], "model_patterns": ["ma5600"]}
        },
        "nokia_alcatel": {
            "snmp": {"sysObjectID": "1.3.6.1.4.1.637"},
            "dhcp": {"circuit_id_pattern": "^ATM [0-9]+:[0-9]+:[0-9]+:[0-9]+$"},
            "dns": {"vendor_patterns": ["nokia", "alu"], "model_patterns": ["isam"]}
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
         patch('src.dslam_detector.DNSAnalyzer') as mock_dns_class:

        detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file=signature_file)
        detector.ghs_analyzer = mock_ghs_class.return_value
        detector.dhcp_analyzer = mock_dhcp_class.return_value
        detector.dns_analyzer = mock_dns_class.return_value
        yield detector


def test_detect_via_snmp_success(dslam_detector, mock_ssh_interface):
    """Tests successful vendor identification using the SNMP method."""
    huawei_oid = "1.3.6.1.4.1.2011.2.82.8"
    mock_ssh_interface.execute_command.return_value = (huawei_oid, "")
    results = dslam_detector._detect_via_snmp()
    assert len(results) == 1
    assert results[0]['vendor'] == 'huawei'
    assert results[0]['confidence'] == dslam_detector.SNMP_MATCH_SCORE

def test_detect_via_dhcp_success(dslam_detector):
    """Tests successful vendor identification using the DHCP method."""
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = ALCATEL_DHCP_ANALYSIS
    results = dslam_detector._detect_via_dhcp()
    assert len(results) == 1
    assert results[0]['vendor'] == 'nokia_alcatel'
    assert results[0]['confidence'] == dslam_detector.DHCP_MATCH_SCORE

def test_detect_via_dns_success(dslam_detector):
    """Tests successful vendor identification using the DNS method."""
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = ZTE_DNS_HOSTNAME
    results = dslam_detector._detect_via_dns()
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'zte'
    assert result['confidence'] == dslam_detector.DNS_VENDOR_SCORE + dslam_detector.DNS_MODEL_SCORE
    assert "zte" in result['description']
    assert "c320" in result['description']

def test_detect_via_dns_vendor_only(dslam_detector):
    """Tests a partial DNS match on only the vendor pattern."""
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = HUAWEI_DNS_HOSTNAME
    results = dslam_detector._detect_via_dns()
    assert len(results) == 1
    result = results[0]
    assert result['vendor'] == 'huawei'
    assert result['confidence'] == dslam_detector.DNS_VENDOR_SCORE

def test_detect_via_dns_no_match(dslam_detector):
    """Tests DNS detection when the hostname matches no patterns."""
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = "unremarkable.isp.com"
    results = dslam_detector._detect_via_dns()
    assert len(results) == 0

def test_detect_via_dns_lookup_fails(dslam_detector):
    """Tests DNS detection when the reverse lookup returns None."""
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = None
    results = dslam_detector._detect_via_dns()
    assert len(results) == 0

def test_identify_vendor_dns_is_best_match(dslam_detector, mock_ssh_interface):
    """Tests that the best result is chosen when DNS has the highest confidence."""
    # Mock other methods to fail
    dslam_detector.ghs_analyzer.capture_and_analyze.return_value = None
    dslam_detector.dhcp_analyzer.capture_and_analyze.return_value = None
    mock_ssh_interface.execute_command.return_value = ("", "Timeout") # SNMP fails

    # DNS provides a match
    dslam_detector.dns_analyzer.get_hostname_by_ip.return_value = ZTE_DNS_HOSTNAME

    result = dslam_detector.identify_vendor(methods=['g_hs', 'snmp', 'dhcp', 'dns'])

    assert result is not None
    assert result['vendor'] == 'zte'
    assert result['confidence'] == dslam_detector.DNS_VENDOR_SCORE + dslam_detector.DNS_MODEL_SCORE