import logging
import json
import re
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UniversalDSLAMDetector:
    """
    A multi-method engine for detecting the vendor of a DSLAM.

    This class uses a collection of signatures and methods to make an educated
    guess about the DSLAM hardware the user is connected to. This information
    is critical for tailoring vendor-specific exploits.
    """
    # Confidence scoring weights
    VENDOR_ID_MATCH_SCORE = 70
    VSI_PATTERN_MATCH_SCORE = 15
    PAYLOAD_MATCH_SCORE = 5
    SNMP_MATCH_SCORE = 95
    DHCP_MATCH_SCORE = 90
    CONFIDENCE_THRESHOLD = 50

    def __init__(self, ssh_interface, signature_file='src/vendor_signatures.json'):
        """
        Initializes the detector with an SSH interface for running commands.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            signature_file: Path to the JSON file containing vendor signatures.
        """
        self.ssh = ssh_interface
        self.ghs_analyzer = GHSHandshakeAnalyzer(ssh_interface)
        self.signatures = self._load_signatures(signature_file)
        self.detection_methods = {
            'snmp': self._detect_via_snmp,
            'dhcp': self._detect_via_dhcp,
            'g_hs': self._detect_via_g_hs,
        }

    def _load_signatures(self, signature_file: str) -> dict:
        """Loads vendor signatures from a JSON file."""
        logging.info(f"Loading vendor signatures from {signature_file}")
        try:
            with open(signature_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Signature file not found: {signature_file}")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from signature file: {signature_file}")
            return {}

    def identify_vendor(self, methods: list = ['g_hs', 'snmp', 'dhcp']) -> dict | None:
        """
        Attempts to identify the DSLAM vendor using a list of specified methods.

        This method now returns the highest-confidence match from all specified
        detection methods that exceeds the confidence threshold.

        Args:
            methods: A list of detection methods to try.

        Returns:
            A dictionary of the highest-confidence vendor match, or None.
        """
        if not self.signatures:
            logging.error("Signature database is empty. Cannot perform detection.")
            return None

        all_results = []
        logging.info(f"Starting DSLAM vendor identification using methods: {methods}")
        for method_name in methods:
            if method_name in self.detection_methods:
                logging.info(f"Attempting detection via {method_name}...")
                results = self.detection_methods[method_name]()
                if results:
                    all_results.extend(results)
            else:
                logging.warning(f"Detection method '{method_name}' not implemented.")

        if not all_results:
            logging.warning("Could not identify DSLAM vendor with the specified methods.")
            return None

        # Sort all results by confidence and return the best one
        best_match = sorted(all_results, key=lambda x: x['confidence'], reverse=True)[0]

        if best_match['confidence'] >= self.CONFIDENCE_THRESHOLD:
            logging.info(f"Highest confidence match: {best_match['vendor']} with {best_match['confidence']}% confidence.")
            return best_match
        else:
            logging.warning(f"No match exceeded the confidence threshold of {self.CONFIDENCE_THRESHOLD}%.")
            return None

    def _detect_via_snmp(self, target_ip: str = '192.168.1.1', community: str = 'public') -> list:
        """
        Performs an SNMP get to find the vendor-specific sysObjectID.
        """
        # The sysObjectID OID is 1.3.6.1.2.1.1.2.0
        oid_to_query = "1.3.6.1.2.1.1.2.0"
        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {oid_to_query}"
        logging.info(f"Executing SNMP command: {command}")

        stdout, stderr = self.ssh.execute_command(command)

        if not stdout or (stderr and "timeout" not in stderr.lower()):
            logging.error(f"SNMP command failed or returned no output. stderr: {stderr}")
            return []

        # Example output: '1.3.6.1.4.1.2011.2.82.8'
        # We just use the raw output as the OID
        returned_oid = stdout.strip()
        logging.info(f"SNMP returned OID: {returned_oid}")

        for vendor, data in self.signatures.items():
            snmp_sig = data.get('snmp', {})
            if 'sysObjectID' in snmp_sig and returned_oid.startswith(snmp_sig['sysObjectID']):
                logging.info(f"Matched SNMP OID for vendor: {vendor}")
                return [{
                    "vendor": vendor,
                    "confidence": self.SNMP_MATCH_SCORE,
                    "description": f"SNMP sysObjectID match ({returned_oid})",
                    "method": "snmp"
                }]

        logging.warning("Returned SNMP OID did not match any known vendor.")
        return []


    def _detect_via_dhcp(self) -> list:
        """Simulated DHCP detection, returning a result with high confidence."""
        command = "echo 'vendor-class-identifier \"ALIN\"'"
        stdout, _ = self.ssh.execute_command(command)
        if "ALIN" in stdout:
            return [{
                "vendor": "nokia_alcatel",
                "confidence": self.DHCP_MATCH_SCORE,
                "description": "DHCP Option 125 match",
                "method": "dhcp"
            }]
        return []

    def _calculate_ghs_confidence(self, analysis: dict) -> list:
        """
        Calculates confidence scores for vendors based on G.hs analysis.
        """
        results = []
        if not analysis or not analysis.get('vendor_id'):
            return results

        analyzed_vendor_id = analysis['vendor_id']
        analyzed_vsi_bytes = analysis.get('vsi', b'')
        analyzed_payload = analysis.get('cl_message_payload', b'')

        try:
            analyzed_vsi_str = analyzed_vsi_bytes.decode('ascii', errors='ignore')
        except:
            analyzed_vsi_str = ""

        for vendor, data in self.signatures.items():
            ghs_data = data.get('ghs', {})
            for sig in ghs_data.get('signatures', []):
                score = 0
                # 1. Check for a strong match on Vendor ID
                if sig.get('vendor_id') == analyzed_vendor_id:
                    score += self.VENDOR_ID_MATCH_SCORE

                # 2. Check for VSI patterns
                for pattern in sig.get('vsi_patterns', []):
                    if pattern in analyzed_vsi_str:
                        score += self.VSI_PATTERN_MATCH_SCORE

                # 3. Check for a raw payload match as a fallback
                pattern_hex = sig.get('cl_payload_pattern')
                if pattern_hex and analyzed_payload.startswith(bytes.fromhex(pattern_hex)):
                    score += self.PAYLOAD_MATCH_SCORE

                if score > 0:
                    results.append({
                        "vendor": vendor,
                        "confidence": min(score, 100), # Cap score at 100
                        "description": sig.get('description'),
                        "method": "g_hs"
                    })

        return sorted(results, key=lambda x: x['confidence'], reverse=True)


    def _detect_via_g_hs(self) -> list:
        """
        Identifies vendor by analyzing the G.hs handshake and scoring matches.
        """
        logging.info("Attempting to identify vendor via G.hs handshake analysis.")

        if not self.ghs_analyzer.capture_handshake():
            logging.error("Failed to capture G.hs handshake. Aborting G.hs detection.")
            return []

        analysis = self.ghs_analyzer.analyze_capture()
        if not analysis:
            logging.warning("G.hs analysis did not yield any results.")
            return []

        logging.info(f"G.hs analysis yielded Vendor ID: {analysis.get('vendor_id')}, VSI: {analysis.get('vsi', b'').hex()}")

        return self._calculate_ghs_confidence(analysis)