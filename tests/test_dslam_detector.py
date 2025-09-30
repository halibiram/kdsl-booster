import pytest
from unittest.mock import MagicMock, patch
from src.dslam_detector import UniversalDSLAMDetector


@pytest.fixture
def mock_ssh_interface():
    """Provides a mock EntwareSSHInterface for testing."""
    return MagicMock()


@pytest.fixture
def dslam_detector(mock_ssh_interface):
    """
    Provides a UniversalDSLAMDetector instance with a mocked SSH interface and
    a mocked GHSHandshakeAnalyzer.
    """
    # By patching the class, any instance of UniversalDSLAMDetector created
    # within the 'with' block will have its ghs_analyzer attribute pre-mocked.
    with patch('src.dslam_detector.GHSHandshakeAnalyzer') as mock_analyzer_class:
        detector = UniversalDSLAMDetector(mock_ssh_interface)
        # The detector's internal analyzer is now a mock. We can access it
        # for setting return values and asserting calls.
        detector.ghs_analyzer = mock_analyzer_class.return_value
        yield detector


def test_identify_vendor_via_snmp_success(dslam_detector, mock_ssh_interface):
    """
    Tests successful vendor identification using the SNMP method.
    """
    mock_ssh_interface.execute_command.return_value = (
        "HOST-RESOURCES-MIB::hrDeviceDescr.3 = STRING: \"Huawei 1.3.6.1.4.1.2011 Board\"", ""
    )
    vendor = dslam_detector.identify_vendor(methods=['snmp'])
    assert vendor == 'huawei'
    mock_ssh_interface.execute_command.assert_called_once()


def test_identify_vendor_via_dhcp_success(dslam_detector, mock_ssh_interface):
    """
    Tests successful vendor identification using the DHCP method as a fallback.
    """
    mock_ssh_interface.execute_command.side_effect = [
        ("", ""),
        ("vendor-class-identifier \"ALIN\"", "")
    ]
    vendor = dslam_detector.identify_vendor(methods=['snmp', 'dhcp'])
    assert vendor == 'nokia'
    assert mock_ssh_interface.execute_command.call_count == 2


def test_identify_vendor_via_g_hs_success(dslam_detector, mock_ssh_interface):
    """
    Tests successful vendor identification using the G.hs handshake method.
    """
    # Make SNMP and DHCP fail
    mock_ssh_interface.execute_command.return_value = ("", "")
    # Mock the GHSHandshakeAnalyzer's methods to return a valid signature
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = {
        'vendor_signature': UniversalDSLAMDetector.VENDOR_SIGNATURES['zte']['g_hs_pattern']
    }

    vendor = dslam_detector.identify_vendor(methods=['snmp', 'dhcp', 'g_hs'])

    assert vendor == 'zte'
    # Check that G.hs methods were called
    dslam_detector.ghs_analyzer.capture_handshake.assert_called_once()
    dslam_detector.ghs_analyzer.analyze_capture.assert_called_once()
    # Check that SNMP and DHCP were also tried
    assert mock_ssh_interface.execute_command.call_count == 2


def test_identify_vendor_via_g_hs_capture_fails(dslam_detector, mock_ssh_interface):
    """
    Tests that G.hs detection fails gracefully if the packet capture fails.
    """
    mock_ssh_interface.execute_command.return_value = ("", "")
    # Simulate a failure in the capture step
    dslam_detector.ghs_analyzer.capture_handshake.return_value = False

    vendor = dslam_detector.identify_vendor(methods=['g_hs'])

    assert vendor is None
    dslam_detector.ghs_analyzer.capture_handshake.assert_called_once()
    # analyze_capture should not be called if capture fails
    dslam_detector.ghs_analyzer.analyze_capture.assert_not_called()


def test_identify_vendor_no_match(dslam_detector, mock_ssh_interface):
    """
    Tests that the detector returns None when no known signatures are found across all methods.
    """
    mock_ssh_interface.execute_command.return_value = ("Some unknown output", "")
    dslam_detector.ghs_analyzer.capture_handshake.return_value = True
    dslam_detector.ghs_analyzer.analyze_capture.return_value = {
        'vendor_signature': b'\xFF\xFF\xFF'  # An unknown signature
    }

    vendor = dslam_detector.identify_vendor() # Test with default methods

    assert vendor is None
    assert mock_ssh_interface.execute_command.call_count == 2
    dslam_detector.ghs_analyzer.capture_handshake.assert_called_once()


def test_identify_vendor_method_order(dslam_detector, mock_ssh_interface):
    """
    Tests that the detector tries methods in order and stops after the first success.
    """
    # Simulate DHCP succeeding for Nokia
    mock_ssh_interface.execute_command.side_effect = [
        ("", ""),  # SNMP fails
        ("vendor-class-identifier \"ALIN\"", "")  # DHCP succeeds
    ]

    vendor = dslam_detector.identify_vendor() # Default order: ['snmp', 'dhcp', 'g_hs']

    assert vendor == 'nokia'
    # It should have tried SNMP and DHCP, but not G.hs
    assert mock_ssh_interface.execute_command.call_count == 2
    dslam_detector.ghs_analyzer.capture_handshake.assert_not_called()