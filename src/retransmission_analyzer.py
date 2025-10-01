"""
This module provides the RetransmissionAnalyzer class, responsible for
discovering and profiling DSL retransmission (G.inp) capabilities of a DSLAM.
"""
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RetransmissionAnalyzer:
    """
    Analyzes and detects DSL retransmission (G.inp) support and configuration.
    """

    def __init__(self, ghs_analyzer, ssh_interface, signatures):
        """
        Initializes the analyzer with necessary components.
        """
        self.ghs_analyzer = ghs_analyzer
        self.ssh = ssh_interface
        self.signatures = signatures

    def detect_retransmission_from_ghs(self) -> dict | None:
        """
        Detects G.inp support from the G.994.1 handshake.
        """
        logging.info("Attempting to detect G.inp capabilities from G.hs handshake...")
        analysis = self.ghs_analyzer.analyze_capture()

        if not analysis or analysis.get('g_inp_bitmap') is None:
            logging.warning("G.inp bitmap not found in G.hs analysis.")
            return None

        bitmap = analysis['g_inp_bitmap']
        # Per G.998.4, for the G.inp parameter (0xB0), the first bit indicates support.
        g_inp_supported = (bitmap & 0b1) == 1

        return {
            "g_inp_supported": g_inp_supported,
            "source": "G.hs Handshake (CL Message)",
            "raw_data": f"Bitmap: {bin(bitmap)}"
        }

    def detect_retransmission_from_snmp(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict | None:
        """
        Detects if G.inp is active by querying a vendor-specific SNMP OID.
        """
        logging.info(f"Attempting to detect active G.inp state from SNMP for vendor: {vendor}...")
        vendor_snmp_sig = self.signatures.get(vendor, {}).get('snmp', {})
        status_config = vendor_snmp_sig.get('retransmission_status')

        if not status_config or 'oid' not in status_config or 'status_mapping' not in status_config:
            logging.warning(f"Incomplete retransmission status SNMP config for vendor '{vendor}' in signatures.")
            return None

        status_oid = status_config['oid']
        status_mapping = status_config['status_mapping']

        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {status_oid}"
        try:
            stdout, stderr = self.ssh.execute_command(command)
            if not stdout or (stderr and "timeout" not in stderr.lower()):
                if stderr: logging.warning(f"SNMP command for retransmission status failed: {stderr.strip()}")
                return None
        except Exception as e:
            logging.error(f"An exception occurred during SNMP retransmission query: {e}", exc_info=True)
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
            logging.warning(f"Could not parse a valid retransmission status from SNMP output: '{output_str}'")
            return None

        return {
            "is_active": is_active,
            "source": "SNMP Query",
            "raw_data": f"OID: {status_oid}, Value: {output_str}"
        }

    def detect_all_retransmission_capabilities(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict:
        """
        Runs all available retransmission detection methods and consolidates the results
        into a comprehensive profile.
        """
        logging.info(f"Running all retransmission detection methods for vendor: {vendor}...")
        detailed_findings = []
        g_inp_supported = False
        is_active = False

        # --- G.hs Method for Hardware Capability ---
        ghs_result = self.detect_retransmission_from_ghs()
        if ghs_result:
            detailed_findings.append(ghs_result)
            if ghs_result.get("g_inp_supported"):
                g_inp_supported = True

        # --- SNMP Method for Operational State ---
        snmp_result = self.detect_retransmission_from_snmp(vendor, target_ip=target_ip, community=community)
        if snmp_result:
            detailed_findings.append(snmp_result)
            if snmp_result.get("is_active"):
                is_active = True

        # --- Final Consolidated Profile ---
        return {
            "g_inp_supported": g_inp_supported,
            "is_active": is_active,
            "detailed_findings": detailed_findings
        }