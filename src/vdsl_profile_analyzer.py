"""
This module provides the VDSLProfileAnalyzer class, which is responsible
for discovering and profiling VDSL2 capabilities of a DSLAM.
"""
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import re

class VDSLProfileAnalyzer:
    """
    Analyzes and detects supported VDSL2 profiles using multiple methods.
    """

    def __init__(self, ghs_analyzer, ssh_interface, signatures):
        """
        Initializes the analyzer with necessary components.
        """
        self.ghs_analyzer = ghs_analyzer
        self.ssh = ssh_interface
        self.signatures = signatures

    def detect_profiles_from_ghs(self) -> dict | None:
        """
        Detects VDSL2 profiles by analyzing the G.994.1 handshake.
        """
        logging.info("Attempting to detect VDSL2 profiles from G.hs handshake...")
        analysis = self.ghs_analyzer.analyze_capture()

        if not analysis or analysis.get('vdsl2_profiles_bitmap') is None:
            logging.warning("VDSL2 profiles bitmap not found in G.hs analysis.")
            return None

        bitmap = analysis['vdsl2_profiles_bitmap']
        supported_profiles = self._parse_vdsl2_profile_bitmap(bitmap)

        return {
            "supported_profiles": supported_profiles,
            "source": "G.hs Handshake (CL Message)",
            "raw_data": f"Bitmap: {bitmap}"
        }

    def detect_profiles_from_snmp(self, vendor: str, target_ip: str = '192.168.1.1', community: str = 'public') -> dict | None:
        """
        Detects VDSL2 profiles by querying vendor-specific SNMP OIDs.
        """
        logging.info(f"Attempting to detect VDSL2 profiles from SNMP for vendor: {vendor}...")
        vendor_snmp_sig = self.signatures.get(vendor, {}).get('snmp', {})
        profiles_oid = vendor_snmp_sig.get('vdsl_profiles_oid')

        if not profiles_oid:
            logging.warning(f"No VDSL2 profiles OID found for vendor '{vendor}' in signatures.")
            return None

        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {profiles_oid}"
        try:
            stdout, stderr = self.ssh.execute_command(command)
            if not stdout or (stderr and "timeout" not in stderr.lower()):
                if stderr: logging.warning(f"SNMP command for profiles failed: {stderr.strip()}")
                return None
        except Exception as e:
            logging.error(f"An exception occurred during SNMP profile query: {e}", exc_info=True)
            return None

        # Parse the SNMP output, which can be in various formats (e.g., INTEGER: 81, Hex-STRING: 00 51)
        output_str = stdout.strip()
        bitmap = 0
        if "no such object" in output_str.lower():
            logging.warning(f"SNMP OID {profiles_oid} not found on target.")
            return None

        match = re.search(r'INTEGER:\s*(\d+)', output_str, re.IGNORECASE)
        if match:
            bitmap = int(match.group(1))
        else:
            match = re.search(r'Hex-STRING:\s*([0-9A-Fa-f\s]+)', output_str, re.IGNORECASE)
            if match:
                hex_str = match.group(1).replace(" ", "")
                if len(hex_str) > 0:
                    bitmap = int(hex_str, 16)

        if bitmap == 0:
            logging.warning(f"Could not parse a valid bitmap from SNMP output: '{output_str}'")
            return None

        supported_profiles = self._parse_vdsl2_profile_bitmap(bitmap)

        return {
            "supported_profiles": supported_profiles,
            "source": "SNMP Query",
            "raw_data": f"OID: {profiles_oid}, Value: {output_str}"
        }

    def detect_all_profiles(self, vendor: str) -> dict:
        """
        Runs all available VDSL2 profile detection methods and consolidates the results.
        """
        logging.info(f"Running all VDSL2 profile detection methods for vendor: {vendor}...")
        all_findings = []

        # --- G.hs Method ---
        ghs_result = self.detect_profiles_from_ghs()
        if ghs_result:
            all_findings.append(ghs_result)

        # --- SNMP Method ---
        snmp_result = self.detect_profiles_from_snmp(vendor)
        if snmp_result:
            all_findings.append(snmp_result)

        # Consolidate unique profiles from all findings
        unique_profiles = set()
        for finding in all_findings:
            unique_profiles.update(finding.get("supported_profiles", []))

        # Sort for consistent output
        sorted_profiles = sorted(list(unique_profiles))

        return {
            "consolidated_profiles": sorted_profiles,
            "detection_methods_used": len(all_findings),
            "detailed_findings": all_findings
        }

    def _parse_vdsl2_profile_bitmap(self, bitmap: int) -> list:
        """
        Parses the VDSL2 profile bitmap from G.994.1 standard fields.
        The bitmap is defined in ITU-T G.994.1 (02/2019), Table 11-28.
        """
        profiles = {
            0: '8a',
            1: '8b',
            2: '8c',
            3: '8d',
            4: '12a',
            5: '12b',
            6: '17a',
            7: '30a',
            8: '35b',
        }

        supported = []
        for bit, profile_name in profiles.items():
            if (bitmap >> bit) & 1:
                supported.append(profile_name)

        logging.info(f"Parsed bitmap {bin(bitmap)} into profiles: {supported}")
        return supported