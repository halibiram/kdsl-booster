import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, IP, UDP, BOOTP, DHCP
from src.dhcp_analyzer import DHCPAnalyzer


@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    ssh_mock = MagicMock()
    ssh_mock.execute_command.return_value = ("", "listening on eth0")
    return ssh_mock

@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a DHCPAnalyzer with a mocked SSH interface."""
    return DHCPAnalyzer(mock_ssh)


def create_mock_dhcp_packet(options):
    """Helper function to create a Scapy DHCP packet with specified options."""
    dhcp_options = [(opt[0], opt[1]) for opt in options]
    dhcp_options.append(("end", b''))
    return Ether()/IP()/UDP(sport=68, dport=67)/BOOTP()/DHCP(options=dhcp_options)

def build_relay_info_bytes(sub_options):
    """Helper to manually construct the byte value for Option 82."""
    payload = b''
    for code, data in sub_options:
        if code == 'agent_circuit_id': payload += b'\x01' + len(data).to_bytes(1, 'big') + data
        elif code == 'agent_remote_id': payload += b'\x02' + len(data).to_bytes(1, 'big') + data
    return payload

def test_parse_dhcp_packets_with_option_82(analyzer):
    """Tests that the parser correctly extracts Circuit ID and Remote ID."""
    circuit_id = b'huawei-slot-1'
    remote_id = b'mac-address-1'
    relay_info_bytes = build_relay_info_bytes([('agent_circuit_id', circuit_id), ('agent_remote_id', remote_id)])
    packet = create_mock_dhcp_packet([('relay_agent_information', relay_info_bytes)])
    result = analyzer._parse_dhcp_packets([packet])
    assert result is not None
    assert result['circuit_id'] == circuit_id
    assert result['remote_id'] == remote_id

def test_parse_dhcp_packets_malformed_suboption(analyzer):
    """Tests that the parser handles a malformed (truncated) sub-option in Option 82."""
    # Sub-option declares length 10, but payload is only 5 bytes long.
    malformed_relay_info = b'\x01\x0a' + b'12345'
    packet = create_mock_dhcp_packet([('relay_agent_information', malformed_relay_info)])
    result = analyzer._parse_dhcp_packets([packet])
    # The parser should fail gracefully and return no data.
    assert result is None

def test_parse_dhcp_packets_no_option_82(analyzer):
    """Tests that the parser returns None when Option 82 is not present."""
    packet = create_mock_dhcp_packet([('message-type', 'discover')])
    result = analyzer._parse_dhcp_packets([packet])
    assert result is None

@patch('src.dhcp_analyzer.rdpcap')
def test_analyze_capture_file_flow(mock_rdpcap, analyzer, tmp_path):
    """Tests the full analysis flow from file to parsed result."""
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

def test_capture_and_analyze_tcpdump_fails(analyzer, mock_ssh):
    """Tests that the main method returns None if tcpdump fails."""
    mock_ssh.execute_command.return_value = ("", "tcpdump: error")
    result = analyzer.capture_and_analyze()
    assert result is None

@patch('src.dhcp_analyzer.DHCPAnalyzer._analyze_capture_file', return_value=None)
def test_capture_and_analyze_sftp_fails(mock_analyze, analyzer, mock_ssh):
    """Tests that the main method returns None if the analysis (e.g., SFTP) fails."""
    # Ensure tcpdump simulation succeeds
    mock_ssh.execute_command.return_value = ("", "listening on eth0")
    result = analyzer.capture_and_analyze()
    assert result is None
    mock_analyze.assert_called_once()