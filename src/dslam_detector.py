import logging
import json
import re
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer
from src.dhcp_analyzer import DHCPAnalyzer
from src.dns_analyzer import DNSAnalyzer
from src.tr069_analyzer import TR069Analyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UniversalDSLAMDetector:
    """
    A multi-method engine for detecting the vendor of a DSLAM.
    """
    # Confidence scoring weights
    SNMP_MATCH_SCORE = 95
    DHCP_MATCH_SCORE = 90
    GHS_VENDOR_ID_SCORE = 70
    TR069_MANUFACTURER_SCORE = 80
    DNS_VENDOR_SCORE = 25
    DNS_MODEL_SCORE = 15
    GHS_VSI_SCORE = 15
    GHS_PAYLOAD_SCORE = 5
    CONFIDENCE_THRESHOLD = 20

    def __init__(self, ssh_interface, signature_file='src/vendor_signatures.json'):
        """
        Initializes the detector with an SSH interface for running commands.
        """
        self.ssh = ssh_interface
        self.ghs_analyzer = GHSHandshakeAnalyzer(ssh_interface)
        self.dhcp_analyzer = DHCPAnalyzer(ssh_interface)
        self.dns_analyzer = DNSAnalyzer()
        self.tr069_analyzer = TR069Analyzer(ssh_interface)
        self.signatures = self._load_signatures(signature_file)
        self.detection_methods = {
            'snmp': self._detect_via_snmp,
            'dhcp': self._detect_via_dhcp,
            'g_hs': self._detect_via_g_hs,
            'dns': self._detect_via_dns,
            'tr069': self._detect_via_tr069,
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

    def identify_vendor(self, methods: list = ['g_hs', 'snmp', 'dhcp', 'dns', 'tr069']) -> dict | None:
        """
        Attempts to identify the DSLAM vendor using a list of specified methods.
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

        best_match = sorted(all_results, key=lambda x: x['confidence'], reverse=True)[0]

        if best_match['confidence'] >= self.CONFIDENCE_THRESHOLD:
            logging.info(f"Highest confidence match: {best_match['vendor']} with {best_match['confidence']}% confidence.")
            return best_match
        else:
            logging.warning(f"No match exceeded the confidence threshold of {self.CONFIDENCE_THRESHOLD}%.")
            return None

    def _detect_via_tr069(self) -> list:
        """
        Analyzes TR-069 Inform messages to identify the vendor.
        """
        logging.info("Attempting to identify vendor via TR-069 analysis.")
        analysis = self.tr069_analyzer.capture_and_analyze()

        if not analysis or 'manufacturer' not in analysis:
            logging.warning("TR-069 analysis did not yield a manufacturer.")
            return []

        manufacturer = analysis['manufacturer']
        logging.info(f"TR-069 analysis yielded manufacturer: {manufacturer}")

        for vendor, data in self.signatures.items():
            tr069_sig = data.get('tr069', {})
            for pattern in tr069_sig.get('manufacturer_patterns', []):
                if re.search(pattern, manufacturer, re.IGNORECASE):
                    return [{
                        "vendor": vendor,
                        "confidence": self.TR069_MANUFACTURER_SCORE,
                        "description": f"TR-069 Manufacturer match on '{manufacturer}' (pattern: {pattern})",
                        "method": "tr069"
                    }]
        return []

    def _detect_via_dns(self, target_ip: str = '8.8.8.8') -> list:
        """
        Performs a reverse DNS lookup and matches the hostname against patterns.
        """
        hostname = self.dns_analyzer.get_hostname_by_ip(target_ip)
        if not hostname: return []

        results = []
        hostname_lower = hostname.lower()

        for vendor, data in self.signatures.items():
            dns_sig = data.get('dns', {})
            score = 0
            matched_patterns = []
            for pattern in dns_sig.get('vendor_patterns', []):
                if re.search(pattern, hostname_lower):
                    score += self.DNS_VENDOR_SCORE
                    matched_patterns.append(pattern)
            for pattern in dns_sig.get('model_patterns', []):
                if re.search(pattern, hostname_lower):
                    score += self.DNS_MODEL_SCORE
                    matched_patterns.append(pattern)
            if score > 0:
                results.append({"vendor": vendor, "confidence": min(score, 100), "description": f"DNS hostname match on '{hostname}' (patterns: {matched_patterns})", "method": "dns"})
        return sorted(results, key=lambda x: x['confidence'], reverse=True)

    def _detect_via_snmp(self, target_ip: str = '192.168.1.1', community: str = 'public') -> list:
        """
        Performs an SNMP get to find the vendor-specific sysObjectID.
        """
        oid_to_query = "1.3.6.1.2.1.1.2.0"
        command = f"snmpget -v2c -c {community} -t 1 -O vq {target_ip} {oid_to_query}"
        stdout, _ = self.ssh.execute_command(command)
        if not stdout: return []

        returned_oid = stdout.strip()
        for vendor, data in self.signatures.items():
            snmp_sig = data.get('snmp', {})
            if 'sysObjectID' in snmp_sig and returned_oid.startswith(snmp_sig['sysObjectID']):
                return [{"vendor": vendor, "confidence": self.SNMP_MATCH_SCORE, "description": f"SNMP sysObjectID match ({returned_oid})", "method": "snmp"}]
        return []

    def _detect_via_dhcp(self) -> list:
        """
        Analyzes DHCP Option 82 to identify the vendor via the Circuit ID format.
        """
        analysis = self.dhcp_analyzer.capture_and_analyze()
        if not analysis or 'circuit_id' not in analysis: return []

        try:
            circuit_id_str = analysis['circuit_id'].decode('ascii', errors='ignore')
        except:
            return []

        for vendor, data in self.signatures.items():
            dhcp_sig = data.get('dhcp', {})
            if 'circuit_id_pattern' in dhcp_sig:
                pattern = dhcp_sig['circuit_id_pattern']
                if re.match(pattern, circuit_id_str):
                    return [{"vendor": vendor, "confidence": self.DHCP_MATCH_SCORE, "description": f"DHCP Circuit ID match (pattern: {pattern})", "method": "dhcp"}]
        return []

    def _calculate_ghs_confidence(self, analysis: dict) -> list:
        """
        Calculates confidence scores for vendors based on G.hs analysis.
        """
        if not analysis or not analysis.get('vendor_id'): return []

        results = []
        analyzed_vendor_id = analysis['vendor_id']
        analyzed_vsi_bytes = analysis.get('vsi', b'')
        try:
            analyzed_vsi_str = analyzed_vsi_bytes.decode('ascii', errors='ignore')
        except:
            analyzed_vsi_str = ""

        for vendor, data in self.signatures.items():
            ghs_data = data.get('ghs', {})
            for sig in ghs_data.get('signatures', []):
                score = 0
                if sig.get('vendor_id') == analyzed_vendor_id: score += self.GHS_VENDOR_ID_SCORE
                for pattern in sig.get('vsi_patterns', []):
                    if pattern in analyzed_vsi_str: score += self.GHS_VSI_SCORE
                pattern_hex = sig.get('cl_payload_pattern')
                if pattern_hex and analysis.get('cl_message_payload', b'').startswith(bytes.fromhex(pattern_hex)):
                    score += self.GHS_PAYLOAD_SCORE
                if score > 0:
                    results.append({"vendor": vendor, "confidence": min(score, 100), "description": sig.get('description'), "method": "g_hs"})
        return sorted(results, key=lambda x: x['confidence'], reverse=True)

    def _detect_via_g_hs(self) -> list:
        """
        Identifies vendor by analyzing the G.hs handshake and scoring matches.
        """
        analysis = self.ghs_analyzer.capture_and_analyze()
        return self._calculate_ghs_confidence(analysis) if analysis else []