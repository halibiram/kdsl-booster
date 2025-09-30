import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, LLC, Raw
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer

# Sample G.hs Payloads
# These are simplified, representative payloads for testing the parser logic.
# CLR (from client), CL (from DSLAM), MS (from client)
SAMPLE_CLR_PAYLOAD = b'\x01\x01\x02\x03'
SAMPLE_CL_PAYLOAD = b'\x02\x11\x22\x33' # This will be our mock vendor signature
SAMPLE_MS_PAYLOAD = b'\x03\x44\x55\x66'
UNKNOWN_PAYLOAD = b'\x99\xAA\xBB'


@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    return MagicMock()


@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a GHSHandshakeAnalyzer with a mocked SSH interface."""
    return GHSHandshakeAnalyzer(mock_ssh)


def test_parse_ghs_message_known_types(analyzer):
    """Tests that the parser correctly identifies known G.hs message types."""
    clr_msg = analyzer._parse_ghs_message(SAMPLE_CLR_PAYLOAD)
    assert clr_msg is not None
    assert clr_msg['type'] == 'CLR'
    assert clr_msg['payload'] == SAMPLE_CLR_PAYLOAD

    cl_msg = analyzer._parse_ghs_message(SAMPLE_CL_PAYLOAD)
    assert cl_msg is not None
    assert cl_msg['type'] == 'CL'
    assert cl_msg['parameters'] == SAMPLE_CL_PAYLOAD[1:]

    ms_msg = analyzer._parse_ghs_message(SAMPLE_MS_PAYLOAD)
    assert ms_msg is not None
    assert ms_msg['type'] == 'MS'


def test_parse_ghs_message_unknown_type(analyzer):
    """Tests that the parser returns None for an unknown message type."""
    msg = analyzer._parse_ghs_message(UNKNOWN_PAYLOAD)
    assert msg is None


@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_parsing_logic(mock_rdpcap, analyzer, tmp_path):
    """
    Tests the main analysis loop by providing a mock pcap file.
    It ensures that the analyzer correctly processes a sequence of packets.
    """
    # Create a dummy pcap file with sample G.hs packets wrapped in Ethernet frames
    pcap_file = tmp_path / "test.pcap"
    packets = [
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=SAMPLE_CLR_PAYLOAD),
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=SAMPLE_CL_PAYLOAD),
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=SAMPLE_MS_PAYLOAD),
    ]
    wrpcap(str(pcap_file), packets)

    # Mock the rdpcap function to read our dummy file
    mock_rdpcap.return_value = packets
    # Mock the SFTP download to do nothing
    analyzer.ssh.sftp_get.return_value = None

    # Run the analysis
    results = analyzer.analyze_capture()

    # Verify the results
    assert len(results['messages']) == 3
    assert results['messages'][0]['type'] == 'CLR'
    assert results['messages'][1]['type'] == 'CL'
    assert results['messages'][2]['type'] == 'MS'

    # Check that the vendor signature (the first CL message payload) is correctly extracted
    assert results['vendor_signature'] == SAMPLE_CL_PAYLOAD


def test_extract_cl_message_payload(analyzer):
    """Tests the logic for extracting the first CL message payload."""
    messages = [
        {'type': 'CLR', 'payload': SAMPLE_CLR_PAYLOAD},
        {'type': 'CL', 'payload': SAMPLE_CL_PAYLOAD},
        {'type': 'MS', 'payload': SAMPLE_MS_PAYLOAD},
    ]
    signature = analyzer._extract_cl_message_payload(messages)
    assert signature == SAMPLE_CL_PAYLOAD


def test_extract_cl_message_payload_no_cl(analyzer):
    """Tests that an empty byte string is returned if no CL message is found."""
    messages = [
        {'type': 'CLR', 'payload': SAMPLE_CLR_PAYLOAD},
        {'type': 'MS', 'payload': SAMPLE_MS_PAYLOAD},
    ]
    signature = analyzer._extract_cl_message_payload(messages)
    assert signature == b''