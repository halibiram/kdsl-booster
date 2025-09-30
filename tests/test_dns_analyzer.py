import pytest
import socket
from unittest.mock import patch
from src.dns_analyzer import DNSAnalyzer


@pytest.fixture
def analyzer():
    """Fixture to create a DNSAnalyzer."""
    return DNSAnalyzer()


@patch('socket.gethostbyaddr')
def test_get_hostname_by_ip_success(mock_gethostbyaddr, analyzer):
    """Tests a successful reverse DNS lookup."""
    ip_address = "8.8.8.8"
    expected_hostname = "dns.google"
    mock_gethostbyaddr.return_value = (expected_hostname, [], [ip_address])

    hostname = analyzer.get_hostname_by_ip(ip_address)

    assert hostname == expected_hostname
    mock_gethostbyaddr.assert_called_once_with(ip_address)


@patch('socket.gethostbyaddr')
def test_get_hostname_by_ip_host_not_found(mock_gethostbyaddr, analyzer):
    """Tests the handling of a 'host not found' error (herror)."""
    ip_address = "192.168.1.100"
    mock_gethostbyaddr.side_effect = socket.herror("Host not found")

    hostname = analyzer.get_hostname_by_ip(ip_address)

    assert hostname is None
    mock_gethostbyaddr.assert_called_once_with(ip_address)


@patch('socket.gethostbyaddr')
def test_get_hostname_by_ip_other_exception(mock_gethostbyaddr, analyzer):
    """Tests the handling of other unexpected socket errors."""
    ip_address = "10.0.0.1"
    mock_gethostbyaddr.side_effect = socket.gaierror("Some other error")

    hostname = analyzer.get_hostname_by_ip(ip_address)

    assert hostname is None
    mock_gethostbyaddr.assert_called_once_with(ip_address)