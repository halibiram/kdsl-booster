"""
This module provides the PSDAnalyzer class, responsible for
discovering and profiling Power Spectral Density (PSD) limitations of a DSLAM.
"""
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PSDAnalyzer:
    """
    Analyzes and detects PSD mask configurations and limitations.
    """

    def __init__(self, ghs_analyzer, ssh_interface, signatures):
        """
        Initializes the analyzer with necessary components.
        """
        self.ghs_analyzer = ghs_analyzer
        self.ssh = ssh_interface
        self.signatures = signatures

    PSD_MASK_MAP = {
        1: "ETSI Annex A (ADLU-32)",
        2: "ETSI Annex B (ADLU-64)",
        8: "FCC Part 68",
    }

    def detect_psd_from_ghs(self) -> dict | None:
        """
        Detects PSD mask information from the G.994.1 handshake.
        """
        logging.info("Attempting to detect PSD mask from G.hs handshake...")
        analysis = self.ghs_analyzer.analyze_capture()

        if not analysis or analysis.get('psd_mask_id') is None:
            logging.warning("PSD mask ID not found in G.hs analysis.")
            return None

        psd_mask_id = analysis['psd_mask_id']
        psd_mask_name = self.PSD_MASK_MAP.get(psd_mask_id, f"Unknown ID {psd_mask_id}")

        return {
            "psd_mask_class": psd_mask_name,
            "source": "G.hs Handshake (CL Message)",
            "raw_data": f"PSD Mask ID: {psd_mask_id}"
        }

    def detect_psd_from_snmp(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict | None:
        """
        Detects PSD mask by querying a vendor-specific SNMP OID.
        """
        logging.info(f"Attempting to detect PSD mask from SNMP for vendor: {vendor}...")
        vendor_snmp_sig = self.signatures.get(vendor, {}).get('snmp', {})
        psd_oid = vendor_snmp_sig.get('psd_mask_oid')

        if not psd_oid:
            logging.warning(f"No PSD mask OID found for vendor '{vendor}' in signatures.")
            return None

        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {psd_oid}"
        try:
            stdout, stderr = self.ssh.execute_command(command)
            if not stdout or (stderr and "timeout" not in stderr.lower()):
                if stderr: logging.warning(f"SNMP command for PSD mask failed: {stderr.strip()}")
                return None
        except Exception as e:
            logging.error(f"An exception occurred during SNMP PSD query: {e}", exc_info=True)
            return None

        output_str = stdout.strip()
        psd_mask_name = "Unknown"
        if "no such object" not in output_str.lower():
            # SNMP may return an integer ID or a string name
            match_int = re.search(r'INTEGER:\s*(\d+)', output_str, re.IGNORECASE)
            match_str = re.search(r'STRING:\s*"(.+?)"', output_str, re.IGNORECASE)
            if match_int:
                psd_mask_id = int(match_int.group(1))
                psd_mask_name = self.PSD_MASK_MAP.get(psd_mask_id, f"Unknown ID {psd_mask_id}")
            elif match_str:
                psd_mask_name = match_str.group(1)

        if psd_mask_name == "Unknown":
            logging.warning(f"Could not parse a valid PSD mask from SNMP output: '{output_str}'")
            return None

        return {
            "psd_mask_class": psd_mask_name,
            "source": "SNMP Query",
            "raw_data": f"OID: {psd_oid}, Value: {output_str}"
        }

    def detect_all_psd_capabilities(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict:
        """
        Runs all available PSD detection methods and consolidates the results
        into a comprehensive profile.
        """
        logging.info(f"Running all PSD detection methods for vendor: {vendor}...")
        detailed_findings = []
        psd_mask_class = "Unknown"

        # --- G.hs Method ---
        ghs_result = self.detect_psd_from_ghs()
        if ghs_result:
            detailed_findings.append(ghs_result)
            psd_mask_class = ghs_result.get("psd_mask_class", "Unknown")

        # --- SNMP Method ---
        snmp_result = self.detect_psd_from_snmp(vendor, target_ip=target_ip, community=community)
        if snmp_result:
            detailed_findings.append(snmp_result)
            # Prefer the SNMP result as it's more likely to be the active config
            psd_mask_class = snmp_result.get("psd_mask_class", psd_mask_class)

        # --- Final Consolidated Profile ---
        return {
            "psd_mask_class": psd_mask_class,
            "detailed_findings": detailed_findings
        }

    def recommend_psd_mask(self, profile: str = '17a') -> int | None:
        """
        Recommends a PSD mask ID based on the desired VDSL2 profile.

        Args:
            profile: The VDSL2 profile ('17a', '35b', etc.).

        Returns:
            The recommended PSD mask ID, or None if no recommendation is available.
        """
        logging.info(f"Generating PSD mask recommendation for profile: {profile}")
        if '35b' in profile:
            # Profile 35b typically requires more flexible or specific masks.
            # Returning a common Annex M or B mask as a placeholder.
            logging.info("Recommending ETSI Annex B for 35b profile for broader frequency support.")
            return 2 # ETSI Annex B
        elif '17a' in profile:
            # Profile 17a is very common and works well with the standard ETSI mask.
            logging.info("Recommending ETSI Annex A for 17a profile.")
            return 1 # ETSI Annex A
        else:
            logging.warning(f"No specific PSD mask recommendation for profile '{profile}'.")
            return None