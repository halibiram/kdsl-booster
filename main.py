"""
DSLAM Detection Ultra - Main Execution Script
...
- Final Profile Analysis and Recommendations
"""
import logging
import json
from unittest.mock import MagicMock
from src.dslam_detector import UniversalDSLAMDetector
from src.reporting import ReportGenerator
from src.vdsl_profile_analyzer import VDSLProfileAnalyzer
from src.vectoring_analyzer import VectoringAnalyzer
from src.bonding_analyzer import BondingAnalyzer
from src.frequency_analyzer import FrequencyAnalyzer
from src.retransmission_analyzer import RetransmissionAnalyzer
from src.psd_analyzer import PSDAnalyzer
from src.dslam_profiler import DSLAMProfiler
from src.database_manager import DatabaseManager

def main():
    print("🚀 Starting DSLAM Detection, Profiling & Reporting Demonstration 🚀")

    # --- 1. Setup and Initialization ---
    print("\n[Step 1] Initializing components...")
    db_manager = DatabaseManager(signature_file_path='src/vendor_signatures.json')
    signatures = db_manager.get_all_signatures()
    if not signatures:
        logging.critical("Signature database is empty. Aborting.")
        return

    mock_ssh_interface = MagicMock()

    detector = UniversalDSLAMDetector(mock_ssh_interface, db_manager)
    profile_analyzer = VDSLProfileAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    vectoring_analyzer = VectoringAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    bonding_analyzer = BondingAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    frequency_analyzer = FrequencyAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    retransmission_analyzer = RetransmissionAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    psd_analyzer = PSDAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    print("Components initialized successfully.")

    # --- 2. Mocking Detection Method Results ---
    print("\n[Step 2] Mocking analyzer results...")

    huawei_snmp_sigs = signatures.get("huawei", {}).get("snmp", {})
    ghs_analysis_mock = {
        "vendor_id": "HWTC", "vsi": b"MA5608T", "cl_message_payload": b"...",
        "handshake_duration": 195.0, "vdsl2_profiles_bitmap": 81, "g_vector_bitmap": 1,
        "bonding_bitmap": 3, "band_plan_id": 32, "g_inp_bitmap": 1, "psd_mask_id": 1
    }

    def mock_snmp_executor(command: str) -> tuple[str, str]:
        """Mocks the SSH execute_command for SNMP, routing to the correct response."""
        if "1.3.6.1.2.1.1.2.0" in command: return huawei_snmp_sigs.get('sysObjectID'), ""
        if huawei_snmp_sigs.get('bonding_status', {}).get('oid') in command: return "", "Timeout"
        if huawei_snmp_sigs.get('vdsl_profiles_oid') in command: return "Hex-STRING: 00 C0", ""
        if huawei_snmp_sigs.get('vectoring_status', {}).get('oid') in command: return "INTEGER: 2", ""
        if huawei_snmp_sigs.get('max_frequency_oid') in command: return "INTEGER: 17664", ""
        if huawei_snmp_sigs.get('retransmission_status', {}).get('oid') in command: return "INTEGER: 1", ""
        if huawei_snmp_sigs.get('psd_mask_oid') in command: return 'STRING: "ETSI Annex A (ADLU-32)"', ""
        return "", "Timeout"

    detector.ghs_analyzer.analyze_capture = MagicMock(return_value=ghs_analysis_mock)
    mock_ssh_interface.execute_command.side_effect = mock_snmp_executor
    detector.dns_analyzer.get_hostname_by_ip = MagicMock(return_value="dslam-ma5608t-london.huawei.isp.com")
    detector.dhcp_analyzer.capture_and_analyze = MagicMock(return_value=None)
    detector.tr069_analyzer.capture_and_analyze = MagicMock(return_value=None)
    print("Mocks configured for a multi-method Huawei detection.")

    # --- 3. Run Vendor Identification ---
    target_ip = '192.168.1.1'
    community_string = 'public'
    print(f"\n[Step 3] Running multi-method vendor identification for target: {target_ip}...")
    vendor_result = detector.identify_vendor(methods=['g_hs', 'snmp', 'dns', 'timing'])
    if not vendor_result or 'primary_vendor' not in vendor_result:
        print("❌ Vendor identification failed.")
        return

    vendor = vendor_result['primary_vendor']
    print(f"✅ Vendor identification complete. Identified Vendor: {vendor}")
    vendor_result['capability_analysis'] = {}

    # --- 4. Run VDSL2 Profile Detection ---
    print("\n[Step 4] Running multi-method VDSL2 profile detection...")
    profile_result = profile_analyzer.detect_all_profiles(vendor, target_ip=target_ip, community=community_string)
    if profile_result and profile_result['consolidated_profiles']:
        print(f"✅ VDSL2 profile detection complete. Profiles: {profile_result['consolidated_profiles']}")
        vendor_result['capability_analysis']['vdsl2_profiles'] = profile_result
    else:
        print("❌ VDSL2 profile detection failed.")

    # --- 5. Run Vectoring Detection ---
    print("\n[Step 5] Running multi-method vectoring detection...")
    vectoring_result = vectoring_analyzer.detect_all_vectoring_capabilities(vendor, target_ip=target_ip, community=community_string)
    if vectoring_result:
        print(f"✅ Vectoring detection complete. Supported: {vectoring_result['hardware_support']}, Active: {vectoring_result['is_active']}")
        vendor_result['capability_analysis']['vectoring'] = vectoring_result
    else:
        print("❌ Vectoring detection failed.")

    # --- 6. Run Bonding Detection ---
    print("\n[Step 6] Running multi-method bonding detection...")
    bonding_result = bonding_analyzer.detect_all_bonding_capabilities(vendor, target_ip=target_ip, community=community_string)
    if bonding_result:
        standards = ", ".join(bonding_result['supported_standards']) if bonding_result['supported_standards'] else "None"
        print(f"✅ Bonding detection complete. Supported Standards: {standards}, Active: {bonding_result['is_active']}")
        vendor_result['capability_analysis']['bonding'] = bonding_result
    else:
        print("❌ Bonding detection failed.")

    # --- 7. Run Frequency Detection ---
    print("\n[Step 7] Running multi-method frequency detection...")
    freq_result = frequency_analyzer.detect_all_frequency_capabilities(vendor, target_ip=target_ip, community=community_string)
    if freq_result:
        ds_mhz = freq_result.get('max_downstream_mhz', 'N/A')
        us_mhz = freq_result.get('max_upstream_mhz', 'N/A')
        plan = freq_result.get('band_plan', 'N/A')
        print(f"✅ Frequency detection complete. Max DS: {ds_mhz}MHz, Max US: {us_mhz}MHz, Band Plan: {plan}")
        vendor_result['capability_analysis']['frequency'] = freq_result
    else:
        print("❌ Frequency detection failed.")

    # --- 8. Run Retransmission Detection ---
    print("\n[Step 8] Running multi-method retransmission (G.inp) detection...")
    retx_result = retransmission_analyzer.detect_all_retransmission_capabilities(vendor, target_ip=target_ip, community=community_string)
    if retx_result:
        supported = retx_result.get('g_inp_supported')
        active = retx_result.get('is_active')
        print(f"✅ G.inp detection complete. Supported: {supported}, Active: {active}")
        vendor_result['capability_analysis']['retransmission'] = retx_result
    else:
        print("❌ G.inp detection failed.")

    # --- 9. Run PSD Detection ---
    print("\n[Step 9] Running multi-method PSD detection...")
    psd_result = psd_analyzer.detect_all_psd_capabilities(vendor, target_ip=target_ip, community=community_string)
    if psd_result:
        mask = psd_result.get('psd_mask_class', 'N/A')
        print(f"✅ PSD detection complete. Mask: {mask}")
        vendor_result['capability_analysis']['psd'] = psd_result
    else:
        print("❌ PSD detection failed.")

    # --- 10. Run Final Profile Analysis ---
    print("\n[Step 10] Running final profile analysis...")
    profiler = DSLAMProfiler(vendor_result['capability_analysis'])
    analysis_result = profiler.generate_profile_analysis()
    if analysis_result:
        warnings_count = len(analysis_result.get('warnings', []))
        recs_count = len(analysis_result.get('recommendations', []))
        print(f"✅ Profile analysis complete. Warnings: {warnings_count}, Recommendations: {recs_count}")
        vendor_result['capability_analysis']['optimization_analysis'] = analysis_result
    else:
        print("❌ Profile analysis failed.")

    # --- 11. Generate and Display Reports ---
    print("\n[Step 11] Generating and displaying reports...")
    report_generator = ReportGenerator(vendor_result)

    print("\n\n" + "="*20 + " TEXT REPORT " + "="*20)
    print(report_generator.generate_text_report())
    print("\n\n" + "="*20 + " JSON REPORT " + "="*20)
    print(report_generator.generate_json_report())
    print("\n\n" + "="*20 + " CSV REPORT " + "="*20)
    print(report_generator.generate_csv_report())

    print("\n🎉 Demonstration Complete 🎉")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()