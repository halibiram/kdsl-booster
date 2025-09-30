import pytest
from unittest.mock import MagicMock, patch
from scapy.all import wrpcap, Ether, TCP, Raw
from src.tr069_analyzer import TR069Analyzer

# Mock TR-069 Payloads
HUAWEI_INFORM_XML = """
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
  <SOAP-ENV:Body>
    <cwmp:Inform>
      <DeviceId>
        <cwmp:Manufacturer>Huawei</cwmp:Manufacturer>
        <cwmp:ProductClass>HG8245</cwmp:ProductClass>
      </DeviceId>
    </cwmp:Inform>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""
INVALID_XML = "<SOAP-ENV:Envelope><Invalid>"

@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    ssh_mock = MagicMock()
    ssh_mock.execute_command.return_value = ("", "listening on br-lan")
    return ssh_mock

@pytest.fixture
def analyzer(mock_ssh):
    """Fixture to create a TR069Analyzer with a mocked SSH interface."""
    return TR069Analyzer(mock_ssh)

def test_parse_inform_message_success(analyzer):
    """Tests that the parser correctly extracts info from a valid Inform message."""
    result = analyzer._parse_inform_message(HUAWEI_INFORM_XML)
    assert result is not None
    assert result['manufacturer'] == 'Huawei'
    assert result['product_class'] == 'HG8245'

def test_parse_inform_message_invalid_xml(analyzer):
    """Tests that the parser returns None for malformed XML."""
    result = analyzer._parse_inform_message(INVALID_XML)
    assert result is None

@patch('src.tr069_analyzer.rdpcap')
def test_analyze_capture_file_flow(mock_rdpcap, analyzer, tmp_path):
    """Tests the full analysis flow from a mock pcap file."""
    pcap_file = tmp_path / "tr069_capture.pcap"
    http_post_request = (b"POST /acs HTTP/1.1\r\n\r\n" + HUAWEI_INFORM_XML.encode('utf-8'))
    packet = Ether() / TCP() / Raw(load=http_post_request)
    wrpcap(str(pcap_file), [packet])

    # Since the analyzer now checks for the file locally, we need to mock os.path.exists
    with patch('os.path.exists', return_value=True):
        mock_rdpcap.return_value = [packet]
        result = analyzer._analyze_capture_file()

    assert result is not None
    assert result['manufacturer'] == 'Huawei'

def test_analyze_capture_file_not_found(analyzer):
    """Tests that analysis returns None if the capture file doesn't exist."""
    # This test is more direct now that the capture logic is separated.
    with patch('src.tr069_analyzer.rdpcap', side_effect=FileNotFoundError):
        result = analyzer._analyze_capture_file()
        assert result is None

def test_capture_and_analyze_tcpdump_fails(analyzer, mock_ssh):
    """Tests that the main method returns None if tcpdump fails."""
    mock_ssh.execute_command.return_value = ("", "tcpdump: command not found")
    result = analyzer.capture_and_analyze()
    assert result is None

def test_capture_and_analyze_sftp_fails(analyzer, mock_ssh):
    """Tests that the main method returns None if the SFTP download fails."""
    # Ensure tcpdump simulation succeeds
    mock_ssh.execute_command.return_value = ("", "listening on br-lan")
    # Mock the _analyze_capture_file to simulate a failure within it (e.g., SFTP)
    with patch.object(analyzer, '_analyze_capture_file', return_value=None) as mock_analyze:
        result = analyzer.capture_and_analyze()
        assert result is None
        mock_analyze.assert_called_once()