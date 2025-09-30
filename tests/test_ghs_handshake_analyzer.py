import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, LLC, Raw, IP
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer

# Sample G.hs Payloads
SAMPLE_CLR_PAYLOAD = b'\x01\x01\x02\x03'
SAMPLE_MS_PAYLOAD = b'\x03\x44\x55\x66'
HUAWEI_CL_PAYLOAD = b'\x02\x91\x0f\x00\xb5' + b'HWTC' + b'MA5608T\x00\x00'
ALCATEL_CL_PAYLOAD = b'\x02\x91\x10\x00\xb5' + b'ALCL' + b'7330ISAM\x01\x02'

# Malformed Payloads for Error Handling Tests
MALFORMED_LEN_PAYLOAD = b'\x02\x91\xff' # Length byte points beyond payload
TRUNCATED_NSIF_PAYLOAD = b'\x02\x91\x04\x00\xb5ZT' # NSIF is too short for a valid vendor ID


@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    return MagicMock()


@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a GHSHandshakeAnalyzer with a mocked SSH interface."""
    return GHSHandshakeAnalyzer(mock_ssh)


def test_parse_ghs_message_with_valid_nsif(analyzer):
    """Tests that the parser correctly extracts Vendor ID and VSI from a valid NSIF."""
    msg = analyzer._parse_ghs_message(HUAWEI_CL_PAYLOAD)
    assert msg is not None
    assert msg['vendor_id'] == 'HWTC'
    assert msg['vsi'] == b'MA5608T\x00\x00'

def test_parse_ghs_message_malformed_length(analyzer):
    """Tests that the parser handles an NSIF with a length pointing beyond the buffer."""
    msg = analyzer._parse_ghs_message(MALFORMED_LEN_PAYLOAD)
    assert msg is not None
    assert msg['vendor_id'] is None
    assert msg['vsi'] is None

def test_parse_ghs_message_truncated_nsif(analyzer):
    """Tests that the parser handles an NSIF that is too short to be valid."""
    msg = analyzer._parse_ghs_message(TRUNCATED_NSIF_PAYLOAD)
    assert msg is not None
    assert msg['vendor_id'] is None
    assert msg['vsi'] is None

@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_timing_calculation(mock_rdpcap, analyzer):
    """
    Tests that the handshake duration is calculated correctly from packet timestamps.
    """
    p1 = Ether() / LLC(); p1.time = 1000.0
    p2 = Ether() / LLC(); p2.time = 1000.215 # 215ms difference
    mock_rdpcap.return_value = [p1, p2]
    analyzer.ssh.sftp_get.return_value = None
    results = analyzer.analyze_capture()
    assert results is not None
    assert results['handshake_duration'] == pytest.approx(215.0)

@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_no_ghs_packets(mock_rdpcap, analyzer):
    """Tests that the analyzer handles captures with no LLC packets."""
    mock_rdpcap.return_value = [Ether() / IP() for _ in range(3)]
    analyzer.ssh.sftp_get.return_value = None
    results = analyzer.analyze_capture()
    assert results == {}

def test_analyze_capture_sftp_fails(analyzer):
    """Tests that analysis returns an empty dict if the SFTP download fails."""
    analyzer.ssh.sftp_get.side_effect = Exception("SFTP Failed")
    results = analyzer.analyze_capture()
    assert results == {}

def test_analyze_capture_rdpcap_fails(analyzer):
    """Tests that analysis returns an empty dict if scapy fails to read the pcap."""
    analyzer.ssh.sftp_get.return_value = None
    with patch('src.ghs_handshake_analyzer.rdpcap') as mock_rdpcap:
        mock_rdpcap.side_effect = Exception("Scapy read error")
        results = analyzer.analyze_capture()
        assert results == {}