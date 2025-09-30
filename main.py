"""
DSLAM Detection Ultra - Main Execution Script

This script demonstrates the full end-to-end capabilities of the project's
DSLAM vendor detection, capability analysis, and reporting system.

It simulates a multi-method detection scenario for a Huawei DSLAM, covering:
- Vendor Identification
- VDSL2 Profile Detection
- Vectoring Detection
- Bonding Detection
- Frequency Capability Detection
- Retransmission (G.inp) Detection
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

# --- Mock Data Configuration ---
HUAWEI_GHS_ANALYSIS = {
    "vendor_id": "HWTC", "vsi": b"MA5608T", "cl_message_payload": b"...",
    "handshake_duration": 195.0,
    "vdsl2_profiles_bitmap": 81,
    "g_vector_bitmap": 1,
    "bonding_bitmap": 3,
    "band_plan_id": 32,
    "g_inp_bitmap": 1  # G.inp supported
}
HUAWEI_SNMP_SYS_OID = "1.3.6.1.4.1.2011.2.82.8"
HUAWEI_VDSL_PROFILES_OID = "1.3.6.1.4.1.2011.5.14.5.2.1.20"
HUAWEI_VDSL_PROFILES_RESPONSE = "Hex-STRING: 00 C0"
HUAWEI_VECTORING_STATUS_OID = "1.3.6.1.4.1.2011.5.14.5.2.1.22"
HUAWEI_VECTORING_STATUS_RESPONSE = "INTEGER: 1"
HUAWEI_BONDING_STATUS_OID = "1.3.6.1.4.1.2011.5.14.8.1.1.1"
HUAWEI_BONDING_STATUS_RESPONSE = "INTEGER: 1"
HUAWEI_MAX_FREQUENCY_OID = "1.3.6.1.4.1.2011.5.14.5.2.1.15"
HUAWEI_MAX_FREQUENCY_RESPONSE = "INTEGER: 17664"
HUAWEI_RETRANSMISSION_STATUS_OID = "1.3.6.1.4.1.2011.5.14.5.2.1.25"
HUAWEI_RETRANSMISSION_STATUS_RESPONSE = "INTEGER: 1" # Active
HUAWEI_DNS_HOSTNAME = "dslam-ma5608t-london.huawei.isp.com"


def mock_snmp_executor(command: str) -> tuple[str, str]:
    """Mocks the SSH execute_command for SNMP, routing to the correct response."""
    if HUAWEI_VDSL_PROFILES_OID in command: return HUAWEI_VDSL_PROFILES_RESPONSE, ""
    if HUAWEI_VECTORING_STATUS_OID in command: return HUAWEI_VECTORING_STATUS_RESPONSE, ""
    if HUAWEI_BONDING_STATUS_OID in command: return HUAWEI_BONDING_STATUS_RESPONSE, ""
    if HUAWEI_MAX_FREQUENCY_OID in command: return HUAWEI_MAX_FREQUENCY_RESPONSE, ""
    if HUAWEI_RETRANSMISSION_STATUS_OID in command: return HUAWEI_RETRANSMISSION_STATUS_RESPONSE, ""
    if "1.3.6.1.2.1.1.2.0" in command: return HUAWEI_SNMP_SYS_OID, ""
    return "", "Timeout"


def main():
    print("🚀 Starting DSLAM Detection, Profiling & Reporting Demonstration 🚀")

    # --- 1. Setup and Initialization ---
    print("\n[Step 1] Initializing components...")
    mock_ssh_interface = MagicMock()

    try:
        with open('src/vendor_signatures.json', 'r') as f:
            signatures = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load signatures: {e}")
        return

    detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file='src/vendor_signatures.json')
    profile_analyzer = VDSLProfileAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    vectoring_analyzer = VectoringAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    bonding_analyzer = BondingAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    frequency_analyzer = FrequencyAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    retransmission_analyzer = RetransmissionAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    print("Components initialized successfully.")

    # --- 2. Mocking Detection Method Results ---
    print("\n[Step 2] Mocking analyzer results...")
    detector.ghs_analyzer.analyze_capture = MagicMock(return_value=HUAWEI_GHS_ANALYSIS)
    mock_ssh_interface.execute_command.side_effect = mock_snmp_executor
    detector.dns_analyzer.get_hostname_by_ip = MagicMock(return_value=HUAWEI_DNS_HOSTNAME)
    detector.dhcp_analyzer.capture_and_analyze = MagicMock(return_value=None)
    detector.tr069_analyzer.capture_and_analyze = MagicMock(return_value=None)
    print("Mocks configured for a multi-method Huawei detection.")

    # --- 3. Run Vendor Identification ---
    print("\n[Step 3] Running multi-method vendor identification...")
    vendor_result = detector.identify_vendor(methods=['g_hs', 'snmp', 'dns', 'timing'])
    if not vendor_result or 'primary_vendor' not in vendor_result:
        print("❌ Vendor identification failed.")
        return

    vendor = vendor_result['primary_vendor']
    print(f"✅ Vendor identification complete. Identified Vendor: {vendor}")
    vendor_result['capability_analysis'] = {}

    # --- 4. Run VDSL2 Profile Detection ---
    print("\n[Step 4] Running multi-method VDSL2 profile detection...")
    profile_result = profile_analyzer.detect_all_profiles(vendor=vendor)
    if profile_result and profile_result['consolidated_profiles']:
        print(f"✅ VDSL2 profile detection complete. Profiles: {profile_result['consolidated_profiles']}")
        vendor_result['capability_analysis']['vdsl2_profiles'] = profile_result
    else:
        print("❌ VDSL2 profile detection failed.")

    # --- 5. Run Vectoring Detection ---
    print("\n[Step 5] Running multi-method vectoring detection...")
    vectoring_result = vectoring_analyzer.detect_all_vectoring_capabilities(vendor=vendor)
    if vectoring_result:
        print(f"✅ Vectoring detection complete. Supported: {vectoring_result['hardware_support']}, Active: {vectoring_result['is_active']}")
        vendor_result['capability_analysis']['vectoring'] = vectoring_result
    else:
        print("❌ Vectoring detection failed.")

    # --- 6. Run Bonding Detection ---
    print("\n[Step 6] Running multi-method bonding detection...")
    bonding_result = bonding_analyzer.detect_all_bonding_capabilities(vendor=vendor)
    if bonding_result:
        standards = ", ".join(bonding_result['supported_standards']) if bonding_result['supported_standards'] else "None"
        print(f"✅ Bonding detection complete. Supported Standards: {standards}, Active: {bonding_result['is_active']}")
        vendor_result['capability_analysis']['bonding'] = bonding_result
    else:
        print("❌ Bonding detection failed.")

    # --- 7. Run Frequency Detection ---
    print("\n[Step 7] Running multi-method frequency detection...")
    freq_result = frequency_analyzer.detect_all_frequency_capabilities(vendor=vendor)
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
    retx_result = retransmission_analyzer.detect_all_retransmission_capabilities(vendor=vendor)
    if retx_result:
        supported = retx_result.get('g_inp_supported')
        active = retx_result.get('is_active')
        print(f"✅ G.inp detection complete. Supported: {supported}, Active: {active}")
        vendor_result['capability_analysis']['retransmission'] = retx_result
    else:
        print("❌ G.inp detection failed.")

    # --- 9. Generate and Display Reports ---
    print("\n[Step 9] Generating and displaying reports...")
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