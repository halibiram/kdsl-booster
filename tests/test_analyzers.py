"""
Unit tests for the various capability analyzer modules.
"""
import pytest
from unittest.mock import MagicMock

# Import the analyzers to be tested
from src.vdsl_profile_analyzer import VDSLProfileAnalyzer
from src.vectoring_analyzer import VectoringAnalyzer
from src.bonding_analyzer import BondingAnalyzer
from src.frequency_analyzer import FrequencyAnalyzer
from src.retransmission_analyzer import RetransmissionAnalyzer
from src.psd_analyzer import PSDAnalyzer

# --- Fixtures for mocked dependencies ---

@pytest.fixture
def mock_ghs_analyzer():
    """Provides a mocked GHSHandshakeAnalyzer."""
    return MagicMock()

@pytest.fixture
def mock_ssh_interface():
    """Provides a mocked SSH interface."""
    return MagicMock()

@pytest.fixture
def mock_signatures():
    """Provides a sample signatures dictionary."""
    return {
        "huawei": {
            "snmp": {
                "vdsl_profiles_oid": "1.2.3.4.1",
                "vectoring_status": {"oid": "1.2.3.4.2", "status_mapping": {"active": 1, "inactive": 2}},
                "bonding_status": {"oid": "1.2.3.4.3", "status_mapping": {"active": 1, "inactive": 2}},
                "max_frequency_oid": "1.2.3.4.4",
                "retransmission_status": {"oid": "1.2.3.4.5", "status_mapping": {"active": 1, "inactive": 2}},
                "psd_mask_oid": "1.2.3.4.6"
            }
        }
    }

# --- Tests for VDSLProfileAnalyzer ---

def test_vdsl_profile_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """
    Tests successful VDSL2 profile detection from G.hs data.
    Bitmap 81 = 17a, 12a, 8a
    """
    mock_ghs_analyzer.analyze_capture.return_value = {"vdsl2_profiles_bitmap": 81}
    analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_profiles_from_ghs()
    assert result is not None
    assert result["supported_profiles"] == ["8a", "12a", "17a"]
    assert result["source"] == "G.hs Handshake (CL Message)"

def test_vdsl_profile_analyzer_ghs_no_bitmap(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """
    Tests VDSL2 profile detection from G.hs when the bitmap is missing.
    """
    mock_ghs_analyzer.analyze_capture.return_value = {} # No bitmap in analysis
    analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_profiles_from_ghs()
    assert result is None

def test_vdsl_profile_analyzer_snmp_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """
    Tests successful VDSL2 profile detection from SNMP data (Hex-STRING).
    Bitmap 0xC0 = 192 = 30a, 17a
    """
    mock_ssh_interface.execute_command.return_value = ("Hex-STRING: 00 C0", "")
    analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_profiles_from_snmp(vendor="huawei")
    assert result is not None
    assert result["supported_profiles"] == ["17a", "30a"]
    assert result["source"] == "SNMP Query"

def test_vdsl_profile_analyzer_snmp_integer_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """
    Tests successful VDSL2 profile detection from SNMP data (INTEGER).
    Bitmap 81 = 17a, 12a, 8a
    """
    mock_ssh_interface.execute_command.return_value = ("INTEGER: 81", "")
    analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_profiles_from_snmp(vendor="huawei")
    assert result is not None
    assert result["supported_profiles"] == ["8a", "12a", "17a"]

def test_vdsl_profile_analyzer_snmp_failure(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """
    Tests VDSL2 profile detection from SNMP when the command fails.
    """
    mock_ssh_interface.execute_command.return_value = ("", "Timeout")
    analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_profiles_from_snmp(vendor="huawei")
    assert result is None

# --- Tests for VectoringAnalyzer ---

def test_vectoring_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful vectoring detection from G.hs data."""
    mock_ghs_analyzer.analyze_capture.return_value = {"g_vector_bitmap": 1}
    analyzer = VectoringAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_vectoring_from_ghs()
    assert result is not None
    assert result["supports_vectoring"] is True

def test_vectoring_analyzer_ghs_no_support(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests vectoring detection from G.hs when not supported."""
    mock_ghs_analyzer.analyze_capture.return_value = {"g_vector_bitmap": 0}
    analyzer = VectoringAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_vectoring_from_ghs()
    assert result is not None
    assert result["supports_vectoring"] is False

def test_vectoring_analyzer_snmp_active(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests vectoring detection from SNMP when active."""
    active_code = mock_signatures["huawei"]["snmp"]["vectoring_status"]["status_mapping"]["active"]
    # The analyzer expects a dsl_interface object with an ssh attribute.
    mock_dsl_interface = MagicMock()
    mock_dsl_interface.ssh.execute_command.return_value = (f"INTEGER: {active_code}", "")
    analyzer = VectoringAnalyzer(mock_ghs_analyzer, mock_dsl_interface, mock_signatures)
    result = analyzer.detect_vectoring_from_snmp(vendor="huawei")
    assert result is not None
    assert result["is_active"] is True

def test_vectoring_analyzer_snmp_inactive(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests vectoring detection from SNMP when inactive."""
    inactive_code = mock_signatures["huawei"]["snmp"]["vectoring_status"]["status_mapping"]["inactive"]
    # The analyzer expects a dsl_interface object with an ssh attribute.
    mock_dsl_interface = MagicMock()
    mock_dsl_interface.ssh.execute_command.return_value = (f"INTEGER: {inactive_code}", "")
    analyzer = VectoringAnalyzer(mock_ghs_analyzer, mock_dsl_interface, mock_signatures)
    result = analyzer.detect_vectoring_from_snmp(vendor="huawei")
    assert result is not None
    assert result["is_active"] is False

# --- Tests for BondingAnalyzer ---

def test_bonding_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful bonding detection from G.hs data."""
    mock_ghs_analyzer.analyze_capture.return_value = {"bonding_bitmap": 3} # G.998.1 and G.998.2
    analyzer = BondingAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_bonding_from_ghs()
    assert result is not None
    assert "G.998.1 (ATM)" in result["supported_standards"]
    assert "G.998.2 (Ethernet)" in result["supported_standards"]

def test_bonding_analyzer_snmp_active(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests bonding detection from SNMP when active."""
    active_code = mock_signatures["huawei"]["snmp"]["bonding_status"]["status_mapping"]["active"]
    mock_ssh_interface.execute_command.return_value = (f"INTEGER: {active_code}", "")
    analyzer = BondingAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_bonding_from_snmp(vendor="huawei")
    assert result is not None
    assert result["is_active"] is True

# --- Tests for FrequencyAnalyzer ---

def test_frequency_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful frequency detection from G.hs data."""
    mock_ghs_analyzer.analyze_capture.return_value = {"band_plan_id": 32}
    analyzer = FrequencyAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_frequency_from_ghs()
    assert result is not None
    assert result["band_plan"] == "ADLU-32 (Annex A, 17a)"
    assert result["max_downstream_mhz"] == 17.664

def test_frequency_analyzer_snmp_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful frequency detection from SNMP."""
    mock_ssh_interface.execute_command.return_value = ("INTEGER: 30000", "") # 30 MHz
    analyzer = FrequencyAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_frequency_from_snmp(vendor="huawei")
    assert result is not None
    assert result["max_downstream_mhz"] == 30.0

# --- Tests for RetransmissionAnalyzer ---

def test_retransmission_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful G.inp detection from G.hs data."""
    mock_ghs_analyzer.analyze_capture.return_value = {"g_inp_bitmap": 1}
    analyzer = RetransmissionAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_retransmission_from_ghs()
    assert result is not None
    assert result["g_inp_supported"] is True

def test_retransmission_analyzer_snmp_active(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests G.inp detection from SNMP when active."""
    active_code = mock_signatures["huawei"]["snmp"]["retransmission_status"]["status_mapping"]["active"]
    mock_ssh_interface.execute_command.return_value = (f"INTEGER: {active_code}", "")
    analyzer = RetransmissionAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_retransmission_from_snmp(vendor="huawei")
    assert result is not None
    assert result["is_active"] is True

# --- Tests for PSDAnalyzer ---

def test_psd_analyzer_ghs_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful PSD mask detection from G.hs data."""
    mock_ghs_analyzer.analyze_capture.return_value = {"psd_mask_id": 1}
    analyzer = PSDAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_psd_from_ghs()
    assert result is not None
    assert result["psd_mask_class"] == "ETSI Annex A (ADLU-32)"

def test_psd_analyzer_snmp_success(mock_ghs_analyzer, mock_ssh_interface, mock_signatures):
    """Tests successful PSD mask detection from SNMP."""
    mock_ssh_interface.execute_command.return_value = ('STRING: "FCC Part 68"', "")
    analyzer = PSDAnalyzer(mock_ghs_analyzer, mock_ssh_interface, mock_signatures)
    result = analyzer.detect_psd_from_snmp(vendor="huawei")
    assert result is not None
    assert result["psd_mask_class"] == "FCC Part 68"