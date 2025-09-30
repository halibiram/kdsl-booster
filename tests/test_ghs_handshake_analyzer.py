import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, LLC, Raw
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer

# Sample G.hs Payloads
SAMPLE_CLR_PAYLOAD = b'\x01\x01\x02\x03'
SAMPLE_MS_PAYLOAD = b'\x03\x44\x55\x66'
UNKNOWN_PAYLOAD = b'\x99\xAA\xBB'

# Payloads for advanced parsing, including valid and invalid NSIF
# NSIF Length byte is now corrected to match the actual data length.
HUAWEI_CL_PAYLOAD = b'\x02\x91\x0f\x00\xb5' + b'HWTC' + b'MA5608T\x00\x00' # NSIF length is 15 (0x0f)
ALCATEL_CL_PAYLOAD = b'\x02\x91\x10\x00\xb5' + b'ALCL' + b'7330ISAM\x01\x02' # NSIF length is 16 (0x10)
MALFORMED_NSIF_PAYLOAD = b'\x02\x91\x04\x00\xb5ZT' # NSIF is too short for a valid vendor ID
NO_NSIF_PAYLOAD = b'\x02\x81\x01\x01' # A standard capabilities message without NSIF


@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    return MagicMock()


@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a GHSHandshakeAnalyzer with a mocked SSH interface."""
    return GHSHandshakeAnalyzer(mock_ssh)


def test_parse_ghs_message_known_types(analyzer):
    """Tests that the parser correctly identifies basic message types."""
    clr_msg = analyzer._parse_ghs_message(SAMPLE_CLR_PAYLOAD)
    assert clr_msg is not None
    assert clr_msg['type'] == 'CLR'
    assert clr_msg['vendor_id'] is None # No NSIF

    ms_msg = analyzer._parse_ghs_message(SAMPLE_MS_PAYLOAD)
    assert ms_msg is not None
    assert ms_msg['type'] == 'MS'


def test_parse_ghs_message_with_valid_nsif(analyzer):
    """Tests that the parser correctly extracts Vendor ID and VSI from a valid NSIF."""
    msg = analyzer._parse_ghs_message(HUAWEI_CL_PAYLOAD)
    assert msg is not None
    assert msg['type'] == 'CL'
    assert msg['vendor_id'] == 'HWTC'
    assert msg['vsi'] == b'MA5608T\x00\x00'

def test_parse_ghs_message_with_another_valid_nsif(analyzer):
    """Tests another valid NSIF payload."""
    msg = analyzer._parse_ghs_message(ALCATEL_CL_PAYLOAD)
    assert msg is not None
    assert msg['type'] == 'CL'
    assert msg['vendor_id'] == 'ALCL'
    assert msg['vsi'] == b'7330ISAM\x01\x02'

def test_parse_ghs_message_with_malformed_nsif(analyzer):
    """Tests that the parser handles an NSIF that is too short."""
    msg = analyzer._parse_ghs_message(MALFORMED_NSIF_PAYLOAD)
    assert msg is not None
    assert msg['type'] == 'CL'
    assert msg['vendor_id'] is None # Should fail to parse vendor ID
    assert msg['vsi'] is None

def test_parse_ghs_message_without_nsif(analyzer):
    """Tests that the parser handles a message with no NSIF field."""
    msg = analyzer._parse_ghs_message(NO_NSIF_PAYLOAD)
    assert msg is not None
    assert msg['type'] == 'CL'
    assert msg['vendor_id'] is None
    assert msg['vsi'] is None


def test_parse_ghs_message_unknown_type(analyzer):
    """Tests that the parser returns None for an unknown message type."""
    msg = analyzer._parse_ghs_message(UNKNOWN_PAYLOAD)
    assert msg is None


@patch('src.ghs_handshake_analyzer.rdpcap')
def test_analyze_capture_parsing_logic(mock_rdpcap, analyzer, tmp_path):
    """
    Tests the main analysis loop by providing a mock pcap file.
    It ensures that the analyzer correctly processes a sequence of packets and extracts the CL message details.
    """
    # Create a dummy pcap file with sample G.hs packets
    pcap_file = tmp_path / "test.pcap"
    packets = [
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=SAMPLE_CLR_PAYLOAD),
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=HUAWEI_CL_PAYLOAD),
        Ether() / LLC(dsap=0xfe, ssap=0xfe, ctrl=0x03) / Raw(load=SAMPLE_MS_PAYLOAD),
    ]
    wrpcap(str(pcap_file), packets)

    mock_rdpcap.return_value = packets
    analyzer.ssh.sftp_get.return_value = None

    # Run the analysis
    results = analyzer.analyze_capture()

    # Verify the results
    assert results is not None
    assert results['cl_message_payload'] == HUAWEI_CL_PAYLOAD
    assert results['vendor_id'] == 'HWTC'
    assert results['vsi'] == b'MA5608T\x00\x00'
    assert results['full_analysis']['type'] == 'CL'


def test_extract_cl_message(analyzer):
    """Tests the logic for extracting the first CL message dictionary."""
    messages = [
        analyzer._parse_ghs_message(SAMPLE_CLR_PAYLOAD),
        analyzer._parse_ghs_message(ALCATEL_CL_PAYLOAD),
        analyzer._parse_ghs_message(HUAWEI_CL_PAYLOAD), # Second CL should be ignored
    ]
    cl_msg = analyzer._extract_cl_message(messages)
    assert cl_msg is not None
    assert cl_msg['vendor_id'] == 'ALCL'


def test_extract_cl_message_no_cl(analyzer):
    """Tests that None is returned if no CL message is found."""
    messages = [
        analyzer._parse_ghs_message(SAMPLE_CLR_PAYLOAD),
        analyzer._parse_ghs_message(SAMPLE_MS_PAYLOAD),
    ]
    cl_msg = analyzer._extract_cl_message(messages)
    assert cl_msg is None