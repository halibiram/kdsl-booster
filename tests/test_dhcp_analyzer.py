import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, IP, UDP, BOOTP, DHCP
from src.dhcp_analyzer import DHCPAnalyzer


@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    return MagicMock()


@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a DHCPAnalyzer with a mocked SSH interface."""
    return DHCPAnalyzer(mock_ssh)


def create_mock_dhcp_packet(options):
    """Helper function to create a Scapy DHCP packet with specified options."""
    dhcp_options = [(opt[0], opt[1]) for opt in options]
    dhcp_options.append(("end", b''))

    return (
        Ether() / IP() / UDP(sport=68, dport=67) /
        BOOTP() / DHCP(options=dhcp_options)
    )

def build_relay_info_bytes(sub_options):
    """Helper to manually construct the byte value for Option 82."""
    payload = b''
    for code, data in sub_options:
        if code == 'agent_circuit_id':
            # Sub-option code 1
            payload += b'\x01' + len(data).to_bytes(1, 'big') + data
        elif code == 'agent_remote_id':
            # Sub-option code 2
            payload += b'\x02' + len(data).to_bytes(1, 'big') + data
    return payload

def test_parse_dhcp_packets_with_option_82(analyzer):
    """Tests that the parser correctly extracts Circuit ID and Remote ID."""
    circuit_id = b'huawei-slot-1'
    remote_id = b'mac-address-1'
    relay_info_bytes = build_relay_info_bytes([
        ('agent_circuit_id', circuit_id),
        ('agent_remote_id', remote_id)
    ])

    packet = create_mock_dhcp_packet([
        ('message-type', 'discover'),
        ('relay_agent_information', relay_info_bytes)
    ])

    result = analyzer._parse_dhcp_packets([packet])

    assert result is not None
    assert result['circuit_id'] == circuit_id
    assert result['remote_id'] == remote_id

def test_parse_dhcp_packets_circuit_id_only(analyzer):
    """Tests parsing a packet with only the Circuit ID sub-option."""
    circuit_id = b'zte-shelf-2'
    relay_info_bytes = build_relay_info_bytes([('agent_circuit_id', circuit_id)])

    packet = create_mock_dhcp_packet([
        ('message-type', 'request'),
        ('relay_agent_information', relay_info_bytes)
    ])

    result = analyzer._parse_dhcp_packets([packet])

    assert result is not None
    assert result['circuit_id'] == circuit_id
    assert 'remote_id' not in result

def test_parse_dhcp_packets_no_option_82(analyzer):
    """Tests that the parser returns None when Option 82 is not present."""
    packet = create_mock_dhcp_packet([('message-type', 'discover')])

    result = analyzer._parse_dhcp_packets([packet])

    assert result is None

def test_parse_dhcp_packets_no_dhcp_layer(analyzer):
    """Tests that the parser handles packets without a DHCP layer."""
    packet = Ether() / IP() / UDP()

    result = analyzer._parse_dhcp_packets([packet])

    assert result is None

@patch('src.dhcp_analyzer.rdpcap')
def test_analyze_capture_file_flow(mock_rdpcap, analyzer, tmp_path):
    """
    Tests the full analysis flow from file to parsed result.
    """
    pcap_file = tmp_path / "test_dhcp.pcap"
    circuit_id = b'alcatel-atm-1'
    relay_info_bytes = build_relay_info_bytes([('agent_circuit_id', circuit_id)])
    packet = create_mock_dhcp_packet([('relay_agent_information', relay_info_bytes)])

    wrpcap(str(pcap_file), [packet])

    mock_rdpcap.return_value = [packet]
    analyzer.ssh.sftp_get.return_value = None

    result = analyzer._analyze_capture_file()

    assert result is not None
    assert result['circuit_id'] == circuit_id
    analyzer.ssh.sftp_get.assert_called_once_with(analyzer.capture_file_path, "dhcp_capture.pcap")
    mock_rdpcap.assert_called_once_with("dhcp_capture.pcap")