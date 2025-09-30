"""
DSLAM Detection Ultra - Main Execution Script

This script demonstrates the full end-to-end capabilities of the project's
DSLAM vendor detection and reporting system.

It simulates a multi-method detection scenario:
1. Establishes a (mocked) SSH connection.
2. Initializes the UniversalDSLAMDetector.
3. Mocks responses for G.hs, SNMP, and DNS detection methods to simulate finding
   evidence for a specific vendor (Huawei).
4. Runs the main vendor identification process.
5. Initializes the ReportGenerator with the results.
6. Prints a comprehensive report in Text, JSON, and CSV formats.
"""
import logging
from unittest.mock import MagicMock
from src.dslam_detector import UniversalDSLAMDetector
from src.reporting import ReportGenerator

# Mock analysis data to be returned by the mocked analyzers
HUAWEI_GHS_ANALYSIS = {
    "vendor_id": "HWTC",
    "vsi": b"MA5608T",
    "cl_message_payload": b"\x02\x91\x0f\x00\xb5HWTCMA5608T\x00\x00",
    "handshake_duration": 195.0
}
HUAWEI_SNMP_OID = "1.3.6.1.4.1.2011.2.82.8"
HUAWEI_DNS_HOSTNAME = "dslam-ma5608t-london.huawei.isp.com"


def main():
    print("🚀 Starting DSLAM Detection & Reporting Demonstration 🚀")

    # --- 1. Setup and Initialization ---
    print("\n[Step 1] Initializing components...")
    mock_ssh_interface = MagicMock()

    # The detector will be initialized with this mock interface.
    # We will mock the analyzer methods directly on the detector's instances.
    detector = UniversalDSLAMDetector(mock_ssh_interface)
    print("Components initialized successfully.")

    # --- 2. Mocking Detection Method Results ---
    print("\n[Step 2] Mocking analyzer results to simulate a detection scenario...")

    # Simulate a successful G.hs and Timing analysis
    detector.ghs_analyzer.analyze_capture.return_value = HUAWEI_GHS_ANALYSIS

    # Simulate a successful SNMP analysis
    detector.ssh.execute_command.side_effect = lambda cmd: (HUAWEI_SNMP_OID, "") if "snmpget" in cmd else ("", "")

    # Simulate a successful DNS analysis
    detector.dns_analyzer.get_hostname_by_ip.return_value = HUAWEI_DNS_HOSTNAME

    # Simulate failures for other methods
    detector.dhcp_analyzer.capture_and_analyze.return_value = None
    detector.tr069_analyzer.capture_and_analyze.return_value = None

    print("Mocks configured for a multi-method Huawei detection.")

    # --- 3. Run Vendor Identification ---
    print("\n[Step 3] Running multi-method vendor identification...")
    # We specify the methods to run to match our mocked scenario
    final_result = detector.identify_vendor(methods=['g_hs', 'snmp', 'dns', 'timing'])

    if final_result:
        print("✅ Vendor identification complete.")
    else:
        print("❌ Vendor identification failed.")
        return

    # --- 4. Generate and Display Reports ---
    print("\n[Step 4] Generating and displaying reports...")
    report_generator = ReportGenerator(final_result)

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
    # Set logging to a higher level for a cleaner demo output
    logging.basicConfig(level=logging.WARNING)
    main()