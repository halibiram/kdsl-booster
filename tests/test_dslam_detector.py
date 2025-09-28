import pytest
from unittest.mock import MagicMock
from src.dslam_detector import UniversalDSLAMDetector

@pytest.fixture
def mock_ssh_interface():
    """Provides a mock EntwareSSHInterface for testing."""
    return MagicMock()

@pytest.fixture
def dslam_detector(mock_ssh_interface):
    """Provides a UniversalDSLAMDetector instance with a mocked SSH interface."""
    return UniversalDSLAMDetector(mock_ssh_interface)

def test_identify_vendor_via_snmp_success(dslam_detector, mock_ssh_interface):
    """
    Tests successful vendor identification using the SNMP method.
    """
    # Simulate an SNMP output that contains the exact OID pattern the code looks for.
    mock_ssh_interface.execute_command.return_value = (
        "HOST-RESOURCES-MIB::hrDeviceDescr.3 = STRING: \"Huawei 1.3.6.1.4.1.2011 Board\"", ""
    )

    vendor = dslam_detector.identify_vendor(methods=['snmp'])

    assert vendor == 'huawei'
    # Verify that the correct (simulated) command was executed
    mock_ssh_interface.execute_command.assert_called_once()

def test_identify_vendor_via_dhcp_success(dslam_detector, mock_ssh_interface):
    """
    Tests successful vendor identification using the DHCP method as a fallback.
    """
    # Simulate SNMP failing (no output) and DHCP succeeding for Nokia
    mock_ssh_interface.execute_command.side_effect = [
        ("", ""),  # First call for SNMP returns nothing
        ("vendor-class-identifier \"ALIN\"", "") # Second call for DHCP returns Nokia signature
    ]

    vendor = dslam_detector.identify_vendor(methods=['snmp', 'dhcp'])

    assert vendor == 'nokia'
    assert mock_ssh_interface.execute_command.call_count == 2

def test_identify_vendor_no_match(dslam_detector, mock_ssh_interface):
    """
    Tests that the detector returns None when no known signatures are found.
    """
    # Simulate command outputs that do not match any known signatures
    mock_ssh_interface.execute_command.return_value = ("Some unknown output", "")

    vendor = dslam_detector.identify_vendor(methods=['snmp', 'dhcp'])

    assert vendor is None
    assert mock_ssh_interface.execute_command.call_count == 2

def test_identify_vendor_method_order(dslam_detector, mock_ssh_interface):
    """
    Tests that the detector tries methods in the specified order and stops
    after the first successful identification.
    """
    # Simulate an SNMP output that contains the exact OID pattern for Huawei.
    mock_ssh_interface.execute_command.return_value = (
        "UDP: [192.168.1.1]:161->[0.0.0.0] OID: 1.3.6.1.4.1.2011.5.25.1.1.1.0", ""
    )

    vendor = dslam_detector.identify_vendor(methods=['snmp', 'dhcp'])

    assert vendor == 'huawei'
    # Only the first method (SNMP) should have been attempted
    mock_ssh_interface.execute_command.assert_called_once()

def test_unimplemented_method_is_skipped(dslam_detector, mock_ssh_interface):
    """
    Tests that the detector safely skips over methods that are not implemented.
    """
    # Simulate no successful detection from the valid method
    mock_ssh_interface.execute_command.return_value = ("", "")

    # Attempt to run with a non-existent method
    vendor = dslam_detector.identify_vendor(methods=['g_hs', 'dhcp'])

    assert vendor is None
    # It should only call the implemented method (dhcp)
    mock_ssh_interface.execute_command.assert_called_once()