"""
Unit tests for the subprocess-based SNMPManager and its integration
with vendor-specific classes and the UniversalDSLAMDetector.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock

from src.snmp_manager import SNMPManager
from src.vendor_snmp import AdtranSnmp, HuaweiSnmp
from src.dslam_detector import UniversalDSLAMDetector
from src.database_manager import DatabaseManager

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch('src.snmp_manager.subprocess.run') as mock_run:
        yield mock_run

# --- SNMPManager Tests ---

def test_snmp_manager_get_success(mock_subprocess_run):
    """Test a successful SNMP GET operation."""
    # Mock the return value from subprocess.run
    mock_process = MagicMock()
    mock_process.stdout = "SNMPv2-MIB::sysDescr.0 = STRING: \"Mock DSLAM Device\""
    mock_process.returncode = 0
    mock_subprocess_run.return_value = mock_process

    manager = SNMPManager(host='127.0.0.1')
    result = manager.get('1.3.6.1.2.1.1.1.0')

    assert result == 'Mock DSLAM Device'
    mock_subprocess_run.assert_called_once()
    # Verify the '-On' flag is present for numeric OID output
    assert '-On' in mock_subprocess_run.call_args[0][0]

def test_snmp_manager_get_no_value(mock_subprocess_run):
    """Test an SNMP GET that returns no value."""
    mock_process = MagicMock()
    mock_process.stdout = "SNMPv2-MIB::sysDescr.0 = STRING: " # Empty value
    mock_process.returncode = 0
    mock_subprocess_run.return_value = mock_process

    manager = SNMPManager(host='127.0.0.1')
    result = manager.get('1.3.6.1.2.1.1.1.0')

    assert result == ''

def test_snmp_manager_get_command_error(mock_subprocess_run):
    """Test an SNMP GET where the command returns a non-zero exit code."""
    # The mock needs to raise CalledProcessError since check=True is used in the manager
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=['snmpget'], stderr="Timeout: No Response from 127.0.0.1"
    )

    manager = SNMPManager(host='127.0.0.1')
    result = manager.get('1.3.6.1.2.1.1.1.0')

    assert result is None

def test_snmp_manager_set_success(mock_subprocess_run):
    """Test a successful SNMP SET operation."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_subprocess_run.return_value = mock_process

    manager = SNMPManager(host='127.0.0.1')
    result = manager.set('1.2.3.4', 'NewValue', value_type='s')

    assert result is True
    # Check that the value and type were correctly passed to the command
    assert '1.2.3.4' in mock_subprocess_run.call_args[0][0]
    assert 's' in mock_subprocess_run.call_args[0][0]
    assert 'NewValue' in mock_subprocess_run.call_args[0][0]

# --- Vendor-Specific Class Tests ---

def test_adtran_set_line_profile(mock_subprocess_run):
    """Test the Adtran-specific set_line_profile method."""
    mock_process = MagicMock(returncode=0)
    mock_subprocess_run.return_value = mock_process

    adtran_snmp = AdtranSnmp(host='127.0.0.1')
    result = adtran_snmp.set_line_profile('VDSL2_17A', interface_index=3)

    assert result is True
    # Verify the final command arguments
    final_command = mock_subprocess_run.call_args[0][0]
    assert '1.3.6.1.4.1.664.5.53.1.5.1.3' in final_command
    assert 's' in final_command
    assert 'VDSL2_17A' in final_command

def test_huawei_set_line_profile_assignment(mock_subprocess_run):
    """Test the Huawei-specific set_line_profile_assignment method."""
    mock_process = MagicMock(returncode=0)
    mock_subprocess_run.return_value = mock_process

    huawei_snmp = HuaweiSnmp(host='127.0.0.1')
    result = huawei_snmp.set_line_profile_assignment(profile_index=22, interface_index=5)

    assert result is True
    # Verify the final command arguments
    final_command = mock_subprocess_run.call_args[0][0]
    assert '1.3.6.1.4.1.2011.5.14.5.2.1.19.5' in final_command
    assert 'i' in final_command
    assert '22' in final_command

# --- DSLAM Detector Integration Test ---

def test_dslam_detector_snmp_integration(mock_subprocess_run):
    """Test the integration of the subprocess-based SNMPManager into UniversalDSLAMDetector."""
    # Mock the subprocess call to return a Huawei sysObjectID
    mock_process = MagicMock()
    mock_process.stdout = ".1.3.6.1.2.1.1.2.0 = OID: .1.3.6.1.4.1.2011.2.83.1.1"
    mock_process.returncode = 0
    mock_subprocess_run.return_value = mock_process

    # Mock the DatabaseManager
    mock_db_manager = MagicMock(spec=DatabaseManager)
    mock_db_manager.get_all_signatures.return_value = {
        "huawei": {
            "snmp": {
                "sysObjectID": ".1.3.6.1.4.1.2011"
            }
        },
        "adtran": {
            "snmp": {
                "sysObjectID": ".1.3.6.1.4.1.664"
            }
        }
    }

    # Instantiate the detector (no SSH interface needed for this test)
    detector = UniversalDSLAMDetector(
        target_ip='127.0.0.1',
        community_string='public',
        db_manager=mock_db_manager
    )

    # Run the SNMP detection method
    findings = detector._detect_via_snmp()

    # Assert the results
    assert len(findings) == 1
    assert findings[0]['vendor'] == 'huawei'
    assert findings[0]['certainty'] == 100
    # The raw_data should be the numeric OID value
    assert findings[0]['raw_data'] == '.1.3.6.1.4.1.2011.2.83.1.1'
    # Verify the correct OID was requested (without a leading dot)
    assert '1.3.6.1.2.1.1.2.0' in mock_subprocess_run.call_args[0][0]