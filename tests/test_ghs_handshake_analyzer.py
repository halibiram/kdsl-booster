import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, LLC, Raw, IP
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer

# Sample G.hs Payloads
SAMPLE_CLR_PAYLOAD = b'\x01\x01\x02\x03'
SAMPLE_MS_PAYLOAD = b'\x03\x44\x55\x66'
UNKNOWN_PAYLOAD = b'\x99\xAA\xBB'

# Payloads for advanced parsing
HUAWEI_CL_PAYLOAD = b'\x02\x91\x0f\x00\xb5' + b'HWTC' + b'MA5608T\x00\x00'
ALCATEL_CL_PAYLOAD = b'\x02\x91\x10\x00\xb5' + b'ALCL' + b'7330ISAM\x01\x02'


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


@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_timing_calculation(mock_rdpcap, analyzer):
    """
    Tests that the handshake duration is calculated correctly from packet timestamps.
    """
    # Create mock packets and set their timestamps manually
    p1 = Ether() / LLC() / Raw(load=SAMPLE_CLR_PAYLOAD)
    p2 = Ether() / LLC() / Raw(load=HUAWEI_CL_PAYLOAD)
    p3 = Ether() / LLC() / Raw(load=SAMPLE_MS_PAYLOAD)
    p1.time = 1000.0
    p2.time = 1000.1
    p3.time = 1000.215 # 215ms difference

    packets = [p1, p2, p3]
    mock_rdpcap.return_value = packets
    analyzer.ssh.sftp_get.return_value = None

    results = analyzer.analyze_capture()

    assert results is not None
    assert 'handshake_duration' in results
    assert results['handshake_duration'] == pytest.approx(215.0)

@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_full_flow(mock_rdpcap, analyzer):
    """
    Tests the main analysis loop, checking for both parsing logic and timing.
    """
    p1 = Ether() / LLC() / Raw(load=SAMPLE_CLR_PAYLOAD)
    p2 = Ether() / LLC() / Raw(load=ALCATEL_CL_PAYLOAD)
    p1.time = 100.0
    p2.time = 100.15 # 150ms difference

    packets = [p1, p2]
    mock_rdpcap.return_value = packets
    analyzer.ssh.sftp_get.return_value = None

    results = analyzer.analyze_capture()

    assert results is not None
    assert results['cl_message_payload'] == ALCATEL_CL_PAYLOAD
    assert results['vendor_id'] == 'ALCL'
    assert results['handshake_duration'] == pytest.approx(150.0)

@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_no_ghs_packets(mock_rdpcap, analyzer):
    """Tests that the analyzer handles captures with no LLC packets."""
    packets = [Ether() / IP() for _ in range(3)] # Non-GHS packets
    mock_rdpcap.return_value = packets
    analyzer.ssh.sftp_get.return_value = None

    results = analyzer.analyze_capture()
    assert results == {}


def test_extract_cl_message(analyzer):
    """Tests the logic for extracting the first CL message dictionary."""
    messages = [
        analyzer._parse_ghs_message(SAMPLE_CLR_PAYLOAD),
        analyzer._parse_ghs_message(ALCATEL_CL_PAYLOAD),
        analyzer._parse_ghs_message(HUAWEI_CL_PAYLOAD),
    ]
    cl_msg = analyzer._extract_cl_message(messages)
    assert cl_msg is not None
    assert cl_msg['vendor_id'] == 'ALCL'