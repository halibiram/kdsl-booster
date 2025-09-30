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

ZTE_INFORM_XML = """
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
  <SOAP-ENV:Body>
    <cwmp:Inform>
      <DeviceId>
        <cwmp:Manufacturer>ZTE</cwmp:Manufacturer>
        <cwmp:ProductClass>ZXHN H298A</cwmp:ProductClass>
      </DeviceId>
    </cwmp:Inform>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""

INVALID_XML = "<SOAP-ENV:Envelope><Invalid>"
NON_INFORM_XML = "<SOAP-ENV:Envelope><SomeOtherMessage/></SOAP-ENV:Envelope>"

@pytest.fixture
def mock_ssh():
    """Fixture to create a mock EntwareSSHInterface."""
    return MagicMock()

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

def test_parse_inform_message_another_vendor(analyzer):
    """Tests parsing another valid Inform message."""
    result = analyzer._parse_inform_message(ZTE_INFORM_XML)
    assert result is not None
    assert result['manufacturer'] == 'ZTE'
    assert result['product_class'] == 'ZXHN H298A'

def test_parse_inform_message_invalid_xml(analyzer):
    """Tests that the parser returns None for malformed XML."""
    result = analyzer._parse_inform_message(INVALID_XML)
    assert result is None

def test_parse_inform_message_not_inform(analyzer):
    """Tests that the parser returns None for valid XML that is not an Inform message."""
    result = analyzer._parse_inform_message(NON_INFORM_XML)
    assert result is None

@patch('src.tr069_analyzer.rdpcap')
def test_analyze_capture_file_flow(mock_rdpcap, analyzer, tmp_path):
    """Tests the full analysis flow from a mock pcap file."""
    pcap_file = tmp_path / "tr069_capture.pcap"
    http_post_request = (
        b"POST /acs HTTP/1.1\r\n"
        b"Content-Type: text/xml\r\n\r\n"
        + HUAWEI_INFORM_XML.encode('utf-8')
    )
    packet = Ether() / TCP() / Raw(load=http_post_request)

    wrpcap(str(pcap_file), [packet])

    mock_rdpcap.return_value = [packet]

    with patch('builtins.open', MagicMock()):
        with patch('os.path.exists', return_value=True):
             result = analyzer._analyze_capture_file()

    assert result is not None
    assert result['manufacturer'] == 'Huawei'
    mock_rdpcap.assert_called_once_with("tr069_capture.pcap")

def test_analyze_capture_file_not_found(analyzer):
    """Tests that analysis returns None if the capture file doesn't exist."""
    with patch('src.tr069_analyzer.rdpcap') as mock_rdpcap:
        mock_rdpcap.side_effect = FileNotFoundError
        result = analyzer._analyze_capture_file()
        assert result is None