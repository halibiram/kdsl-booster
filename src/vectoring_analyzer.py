"""
This module provides the VectoringAnalyzer class, responsible for
discovering and profiling VDSL2 vectoring (G.993.5) capabilities of a DSLAM.
"""
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VectoringAnalyzer:
    """
    Analyzes and detects VDSL2 vectoring support and configuration.
    """

    def __init__(self, ghs_analyzer, ssh_interface, signatures):
        """
        Initializes the analyzer with necessary components.
        """
        self.ghs_analyzer = ghs_analyzer
        self.ssh = ssh_interface
        self.signatures = signatures

    def detect_vectoring_from_ghs(self) -> dict | None:
        """
        Detects vectoring capabilities from the G.994.1 handshake.
        Parses the G.vector bitmap for hardware support details.
        """
        logging.info("Attempting to detect vectoring capabilities from G.hs handshake...")
        analysis = self.ghs_analyzer.analyze_capture()

        if not analysis or analysis.get('g_vector_bitmap') is None:
            logging.warning("G.vector bitmap not found in G.hs analysis.")
            return None

        bitmap = analysis['g_vector_bitmap']
        # Per G.994.1, for the G.vector parameter (0x86), the bits indicate:
        # Bit 0 (LSB): Support for G.vector over VDSL2
        # Bit 1: Support for G.vector over VDSL2 as an xTU-R
        # We will check the first bit to confirm basic vectoring support.
        supports_vectoring = (bitmap & 0b1) == 1

        return {
            "supports_vectoring": supports_vectoring,
            "source": "G.hs Handshake (CL Message)",
            "raw_data": f"Bitmap: {bin(bitmap)}"
        }

    def detect_vectoring_from_snmp(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict | None:
        """
        Detects if vectoring is currently active by querying a vendor-specific SNMP OID.
        """
        logging.info(f"Attempting to detect active vectoring state from SNMP for vendor: {vendor}...")
        vendor_snmp_sig = self.signatures.get(vendor, {}).get('snmp', {})
        status_config = vendor_snmp_sig.get('vectoring_status')

        if not status_config or 'oid' not in status_config or 'status_mapping' not in status_config:
            logging.warning(f"Incomplete vectoring status SNMP config for vendor '{vendor}' in signatures.")
            return None

        status_oid = status_config['oid']
        status_mapping = status_config['status_mapping']

        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {status_oid}"
        try:
            stdout, stderr = self.ssh.execute_command(command)
            if not stdout or (stderr and "timeout" not in stderr.lower()):
                if stderr: logging.warning(f"SNMP command for vectoring status failed: {stderr.strip()}")
                return None
        except Exception as e:
            logging.error(f"An exception occurred during SNMP vectoring query: {e}", exc_info=True)
            return None

        output_str = stdout.strip()
        is_active = "unknown"
        if "no such object" not in output_str.lower():
            match = re.search(r'\d+', output_str)
            if match:
                status_code = int(match.group(0))
                if status_code == status_mapping.get('active'):
                    is_active = True
                elif status_code == status_mapping.get('inactive'):
                    is_active = False

        if is_active == "unknown":
            logging.warning(f"Could not parse a valid vectoring status from SNMP output: '{output_str}'")
            return None

        return {
            "is_active": is_active,
            "source": "SNMP Query",
            "raw_data": f"OID: {status_oid}, Value: {output_str}"
        }

    def detect_all_vectoring_capabilities(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict:
        """
        Runs all available vectoring detection methods and consolidates the results
        into a comprehensive profile.
        """
        logging.info(f"Running all vectoring detection methods for vendor: {vendor}...")
        detailed_findings = []

        # --- G.hs Method for Hardware Capability ---
        ghs_result = self.detect_vectoring_from_ghs()
        hardware_support = False
        if ghs_result:
            detailed_findings.append(ghs_result)
            if ghs_result.get('supports_vectoring'):
                hardware_support = True

        # --- SNMP Method for Operational State ---
        snmp_result = self.detect_vectoring_from_snmp(vendor, target_ip=target_ip, community=community)
        is_active = False
        if snmp_result:
            detailed_findings.append(snmp_result)
            if snmp_result.get('is_active'):
                is_active = True

        # --- Final Consolidated Profile ---
        return {
            "hardware_support": hardware_support,
            "is_active": is_active,
            "detailed_findings": detailed_findings
        }