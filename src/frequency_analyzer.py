"""
This module provides the FrequencyAnalyzer class, responsible for
discovering and profiling the maximum supported frequencies of a DSLAM.
"""
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FrequencyAnalyzer:
    """
    Analyzes and detects the maximum supported frequencies and band plans.
    """

    def __init__(self, ghs_analyzer, ssh_interface, signatures):
        """
        Initializes the analyzer with necessary components.
        """
        self.ghs_analyzer = ghs_analyzer
        self.ssh = ssh_interface
        self.signatures = signatures

    BAND_PLAN_MAP = {
        32: {"name": "ADLU-32 (Annex A, 17a)", "max_ds_mhz": 17.664, "max_us_mhz": 12.0},
        33: {"name": "ADLU-33 (Annex A, 17a)", "max_ds_mhz": 17.664, "max_us_mhz": 12.0},
        64: {"name": "ADLU-64 (Annex B, 35b)", "max_ds_mhz": 35.328, "max_us_mhz": 19.0},
    }

    def detect_frequency_from_ghs(self) -> dict | None:
        """
        Detects frequency capabilities from the G.994.1 handshake band plan ID.
        """
        logging.info("Attempting to detect frequency capabilities from G.hs handshake...")
        analysis = self.ghs_analyzer.analyze_capture()

        if not analysis or analysis.get('band_plan_id') is None:
            logging.warning("Band plan ID not found in G.hs analysis.")
            return None

        band_plan_id = analysis['band_plan_id']
        band_plan_info = self.BAND_PLAN_MAP.get(band_plan_id)

        if not band_plan_info:
            logging.warning(f"Unknown band plan ID: {band_plan_id}")
            return None

        return {
            "band_plan": band_plan_info["name"],
            "max_downstream_mhz": band_plan_info["max_ds_mhz"],
            "max_upstream_mhz": band_plan_info["max_us_mhz"],
            "source": "G.hs Handshake (CL Message)",
            "raw_data": f"Band Plan ID: {band_plan_id}"
        }

    def detect_frequency_from_snmp(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict | None:
        """
        Detects max frequency by querying a vendor-specific SNMP OID.
        """
        logging.info(f"Attempting to detect max frequency from SNMP for vendor: {vendor}...")
        vendor_snmp_sig = self.signatures.get(vendor, {}).get('snmp', {})
        freq_oid = vendor_snmp_sig.get('max_frequency_oid')

        if not freq_oid:
            logging.warning(f"No max frequency OID found for vendor '{vendor}' in signatures.")
            return None

        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {freq_oid}"
        try:
            stdout, stderr = self.ssh.execute_command(command)
            if not stdout or (stderr and "timeout" not in stderr.lower()):
                if stderr: logging.warning(f"SNMP command for max frequency failed: {stderr.strip()}")
                return None
        except Exception as e:
            logging.error(f"An exception occurred during SNMP frequency query: {e}", exc_info=True)
            return None

        output_str = stdout.strip()
        max_freq_mhz = None
        if "no such object" not in output_str.lower():
            match = re.search(r'\d+', output_str)
            if match:
                # Assuming the value is returned in kHz
                max_freq_mhz = int(match.group(0)) / 1000.0

        if max_freq_mhz is None:
            logging.warning(f"Could not parse a valid frequency from SNMP output: '{output_str}'")
            return None

        return {
            "max_downstream_mhz": max_freq_mhz,
            "source": "SNMP Query",
            "raw_data": f"OID: {freq_oid}, Value: {output_str}"
        }

    def detect_all_frequency_capabilities(self, vendor: str) -> dict:
        """
        Runs all available frequency detection methods and consolidates the results
        into a comprehensive profile.
        """
        logging.info(f"Running all frequency detection methods for vendor: {vendor}...")
        detailed_findings = []
        consolidated_results = {
            "max_downstream_mhz": None,
            "max_upstream_mhz": None,
            "band_plan": "Unknown",
        }

        # --- G.hs Method ---
        ghs_result = self.detect_frequency_from_ghs()
        if ghs_result:
            detailed_findings.append(ghs_result)
            consolidated_results["band_plan"] = ghs_result.get("band_plan", "Unknown")
            consolidated_results["max_downstream_mhz"] = ghs_result.get("max_downstream_mhz")
            consolidated_results["max_upstream_mhz"] = ghs_result.get("max_upstream_mhz")

        # --- SNMP Method ---
        snmp_result = self.detect_frequency_from_snmp(vendor)
        if snmp_result:
            detailed_findings.append(snmp_result)
            # SNMP might provide a more accurate max downstream frequency, so prefer it if available.
            if snmp_result.get("max_downstream_mhz"):
                consolidated_results["max_downstream_mhz"] = snmp_result["max_downstream_mhz"]

        # --- Final Consolidated Profile ---
        consolidated_results["detailed_findings"] = detailed_findings
        return consolidated_results