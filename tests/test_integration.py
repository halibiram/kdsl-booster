"""
Integration test for the full DSLAM capability discovery and profiling workflow.
"""
import pytest
import json
from unittest.mock import MagicMock

# Import all components of the system
from src.dslam_detector import UniversalDSLAMDetector
from src.vdsl_profile_analyzer import VDSLProfileAnalyzer
from src.vectoring_analyzer import VectoringAnalyzer
from src.bonding_analyzer import BondingAnalyzer
from src.frequency_analyzer import FrequencyAnalyzer
from src.retransmission_analyzer import RetransmissionAnalyzer
from src.psd_analyzer import PSDAnalyzer
from src.dslam_profiler import DSLAMProfiler
from src.reporting import ReportGenerator

@pytest.fixture
def signatures():
    """Loads the vendor signatures for use in tests."""
    with open('src/vendor_signatures.json', 'r') as f:
        return json.load(f)

def test_full_end_to_end_workflow(signatures, mocker):
    """
    Tests the complete workflow from vendor detection to final report generation,
    ensuring all components integrate correctly.
    """
    # --- 1. Mocking Setup ---

    # Mock GHS Analysis Response
    ghs_mock_data = {
        "vendor_id": "HWTC", "vsi": b"MA5608T",
        "vdsl2_profiles_bitmap": 81,  # 8a, 12a, 17a
        "g_vector_bitmap": 1,
        "bonding_bitmap": 3,
        "band_plan_id": 32,
        "g_inp_bitmap": 1,
        "psd_mask_id": 1
    }
    mock_ghs_analyzer = MagicMock()
    mock_ghs_analyzer.analyze_capture.return_value = ghs_mock_data

    # Mock SSH Interface and SNMP Responses
    mock_ssh = MagicMock()
    huawei_snmp_sigs = signatures.get("huawei", {}).get("snmp", {})

    def snmp_executor(command):
        # Vendor ID check is for the generic sysObjectID OID
        if "1.3.6.1.2.1.1.2.0" in command:
            return huawei_snmp_sigs.get('sysObjectID'), ""

        # Capability checks are for specific OIDs
        if huawei_snmp_sigs.get('vdsl_profiles_oid') in command:
            return "Hex-STRING: 00 C0", "" # 17a, 30a
        if huawei_snmp_sigs.get('vectoring_status', {}).get('oid') in command:
            return "INTEGER: 2", "" # Inactive

        # Let other SNMP queries "fail" to test graceful handling
        return "", "Timeout"

    mock_ssh.execute_command.side_effect = snmp_executor

    # Mock DNS Analyzer
    mock_dns_analyzer = MagicMock()
    mock_dns_analyzer.get_hostname_by_ip.return_value = "dslam-ma5608t-london.huawei.isp.com"

    # We need to patch the analyzers inside the detector, not just pass them in
    mocker.patch('src.dslam_detector.GHSHandshakeAnalyzer', return_value=mock_ghs_analyzer)
    mocker.patch('src.dslam_detector.DNSAnalyzer', return_value=mock_dns_analyzer)

    # --- 2. Initialization ---
    mock_db_manager = MagicMock()
    mock_db_manager.get_all_signatures.return_value = signatures

    detector = UniversalDSLAMDetector(
        target_ip="127.0.0.1",
        community_string="public",
        db_manager=mock_db_manager,
        ssh_interface=mock_ssh
    )
    profile_analyzer = VDSLProfileAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)
    vectoring_analyzer = VectoringAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)
    bonding_analyzer = BondingAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)
    frequency_analyzer = FrequencyAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)
    retransmission_analyzer = RetransmissionAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)
    psd_analyzer = PSDAnalyzer(mock_ghs_analyzer, mock_ssh, signatures)

    # --- 3. Execution ---

    # Vendor Detection
    vendor_result = detector.identify_vendor()
    vendor = vendor_result['primary_vendor']
    vendor_result['capability_analysis'] = {}

    # Capability Analysis
    vendor_result['capability_analysis']['vdsl2_profiles'] = profile_analyzer.detect_all_profiles(vendor, "1.1.1.1", "public")
    vendor_result['capability_analysis']['vectoring'] = vectoring_analyzer.detect_all_vectoring_capabilities(vendor, "1.1.1.1", "public")
    vendor_result['capability_analysis']['bonding'] = bonding_analyzer.detect_all_bonding_capabilities(vendor, "1.1.1.1", "public")
    vendor_result['capability_analysis']['frequency'] = frequency_analyzer.detect_all_frequency_capabilities(vendor, "1.1.1.1", "public")
    vendor_result['capability_analysis']['retransmission'] = retransmission_analyzer.detect_all_retransmission_capabilities(vendor, "1.1.1.1", "public")
    vendor_result['capability_analysis']['psd'] = psd_analyzer.detect_all_psd_capabilities(vendor, "1.1.1.1", "public")

    # Profiling
    profiler = DSLAMProfiler(vendor_result['capability_analysis'])
    vendor_result['capability_analysis']['optimization_analysis'] = profiler.generate_profile_analysis()

    # Reporting
    report_generator = ReportGenerator(vendor_result)
    final_report = report_generator.generate_text_report()

    # --- 4. Assertion ---
    assert "Vendor: huawei" in final_report
    assert "Supported Profiles: 12a, 17a, 30a, 8a" in final_report
    assert "Hardware Support: Yes" in final_report
    assert "Currently Active: No" in final_report # Vectoring is inactive
    assert "Suboptimal Configuration: Vectoring" in final_report # Check for the correct warning
    assert "Inconsistency: Profile 30a" in final_report # The 30a warning SHOULD trigger from G.hs data
    assert "PSD Mask Class: ETSI Annex A (ADLU-32)" in final_report