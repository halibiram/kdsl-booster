"""
DSLAM Detection Ultra - Main Execution Script

This script demonstrates the full end-to-end capabilities of the project's
DSLAM vendor detection, capability analysis, and reporting system.

It simulates a multi-method detection scenario:
1. Establishes a (mocked) SSH connection.
2. Initializes the UniversalDSLAMDetector and VDSLProfileAnalyzer.
3. Mocks responses for G.hs, SNMP, and DNS detection methods to simulate finding
   evidence for a specific vendor (Huawei) and its VDSL2 capabilities.
4. Runs the main vendor identification process.
5. Runs the multi-method VDSL2 profile detection process.
6. Initializes the ReportGenerator with the results.
7. Prints a comprehensive report in Text, JSON, and CSV formats.
"""
import logging
import json
from unittest.mock import MagicMock
from src.dslam_detector import UniversalDSLAMDetector
from src.reporting import ReportGenerator
from src.vdsl_profile_analyzer import VDSLProfileAnalyzer

# --- Mock Data Configuration ---
# G.hs mock data: Bitmap for profiles 17a, 12a, 8a -> (1<<6)|(1<<4)|(1<<0) = 81
HUAWEI_GHS_ANALYSIS = {
    "vendor_id": "HWTC",
    "vsi": b"MA5608T",
    "cl_message_payload": b"\x02\x83\x02\x00\x51\x91\x0f...",
    "handshake_duration": 195.0,
    "vdsl2_profiles_bitmap": 81
}
# SNMP mock data: OID for vendor detection
HUAWEI_SNMP_SYS_OID = "1.3.6.1.4.1.2011.2.82.8"
# SNMP mock data: OID and response for VDSL2 profiles
# Bitmap for profiles 30a, 17a -> (1<<7)|(1<<6) = 192. Response as Hex-String.
HUAWEI_VDSL_PROFILES_OID = "1.3.6.1.4.1.2011.5.14.5.2.1.20"
HUAWEI_VDSL_PROFILES_RESPONSE = "Hex-STRING: 00 C0"
# DNS mock data
HUAWEI_DNS_HOSTNAME = "dslam-ma5608t-london.huawei.isp.com"


def mock_snmp_executor(command: str) -> tuple[str, str]:
    """Mocks the SSH execute_command for SNMP, routing to the correct response."""
    if HUAWEI_VDSL_PROFILES_OID in command:
        return HUAWEI_VDSL_PROFILES_RESPONSE, ""
    if "1.3.6.1.2.1.1.2.0" in command: # sysObjectID OID
        return HUAWEI_SNMP_SYS_OID, ""
    return "", "Timeout"


def main():
    print("🚀 Starting DSLAM Detection, Profiling & Reporting Demonstration 🚀")

    # --- 1. Setup and Initialization ---
    print("\n[Step 1] Initializing components...")
    mock_ssh_interface = MagicMock()

    # Load signatures to be used by analyzers
    try:
        with open('src/vendor_signatures.json', 'r') as f:
            signatures = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load signatures: {e}")
        return

    detector = UniversalDSLAMDetector(mock_ssh_interface, signature_file='src/vendor_signatures.json')
    profile_analyzer = VDSLProfileAnalyzer(detector.ghs_analyzer, mock_ssh_interface, signatures)
    print("Components initialized successfully.")

    # --- 2. Mocking Detection Method Results ---
    print("\n[Step 2] Mocking analyzer results to simulate a detection scenario...")

    # Mock G.hs analysis
    detector.ghs_analyzer.analyze_capture = MagicMock(return_value=HUAWEI_GHS_ANALYSIS)

    # Mock SNMP command execution to route based on OID
    mock_ssh_interface.execute_command.side_effect = mock_snmp_executor

    # Mock DNS analysis
    detector.dns_analyzer.get_hostname_by_ip = MagicMock(return_value=HUAWEI_DNS_HOSTNAME)

    # Mock other analyzers to fail gracefully
    detector.dhcp_analyzer.capture_and_analyze = MagicMock(return_value=None)
    detector.tr069_analyzer.capture_and_analyze = MagicMock(return_value=None)

    print("Mocks configured for a multi-method Huawei detection.")

    # --- 3. Run Vendor Identification ---
    print("\n[Step 3] Running multi-method vendor identification...")
    vendor_result = detector.identify_vendor(methods=['g_hs', 'snmp', 'dns', 'timing'])

    if not vendor_result or 'primary_vendor' not in vendor_result:
        print("❌ Vendor identification failed.")
        return

    print(f"✅ Vendor identification complete. Identified Vendor: {vendor_result['primary_vendor']}")

    # --- 4. Run Multi-Method VDSL2 Profile Detection ---
    print("\n[Step 4] Running multi-method VDSL2 profile detection...")
    profile_result = profile_analyzer.detect_all_profiles(vendor=vendor_result['primary_vendor'])

    if profile_result and profile_result['consolidated_profiles']:
        print("✅ VDSL2 profile detection complete.")
        print(f"   Consolidated Profiles: {profile_result['consolidated_profiles']}")
        # Combine results for final report
        vendor_result['capability_analysis'] = {"vdsl2_profiles": profile_result}
    else:
        print("❌ VDSL2 profile detection failed.")

    # --- 5. Generate and Display Reports ---
    print("\n[Step 5] Generating and displaying reports...")
    report_generator = ReportGenerator(vendor_result)

    # --- Text Report ---
    print("\n\n" + "="*20 + " TEXT REPORT " + "="*20)
    print(report_generator.generate_text_report())

    # --- JSON Report ---
    print("\n\n" + "="*20 + " JSON REPORT " + "="*20)
    print(report_generator.generate_json_report())

    # --- CSV Report ---
    print("\n\n" + "="*20 + " CSV REPORT " + "="*20)
    print(report_generator.generate_csv_report())

    print("\n🎉 Demonstration Complete 🎉")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()