import logging
import json
import re
from collections import defaultdict
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer
from src.dhcp_analyzer import DHCPAnalyzer
from src.dns_analyzer import DNSAnalyzer
from src.tr069_analyzer import TR069Analyzer
from src.snmp_manager import SNMPManager
from src.snmp_mib_library import SYSTEM_OIDS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UniversalDSLAMDetector:
    """
    A multi-method engine for detecting the vendor of a DSLAM.
    """
    # Formal weighting scheme as per Task 7
    METHOD_WEIGHTS = {
        "g_hs": 35,
        "snmp": 30,
        "dhcp": 20,
        "dns": 10,
        "tr069": 4,
        "timing": 1,
    }
    # Certainty scores for sub-findings within a method
    GHS_VENDOR_ID_CERTAINTY = 70
    GHS_VSI_CERTAINTY = 25
    DNS_VENDOR_CERTAINTY = 80
    DNS_MODEL_CERTAINTY = 20
    # A final score must be above this threshold to be considered a valid result.
    FINAL_CONFIDENCE_THRESHOLD = 10

    def __init__(self, target_ip, community_string, db_manager, ssh_interface=None):
        """
        Initializes the detector.
        """
        self.target_ip = target_ip
        self.community_string = community_string
        self.db_manager = db_manager
        self.signatures = self.db_manager.get_all_signatures()
        self.ssh = ssh_interface # Keep for non-SNMP methods

        # Initialize analyzers
        self.ghs_analyzer = GHSHandshakeAnalyzer(ssh_interface)
        self.dhcp_analyzer = DHCPAnalyzer(ssh_interface)
        self.dns_analyzer = DNSAnalyzer()
        self.tr069_analyzer = TR069Analyzer(ssh_interface)
        self.snmp_manager = SNMPManager(host=target_ip, community=community_string)

        self.detection_methods = {
            'g_hs': self._detect_via_g_hs,
            'snmp': self._detect_via_snmp,
            'dhcp': self._detect_via_dhcp,
            'dns': self._detect_via_dns,
            'tr069': self._detect_via_tr069,
            'timing': self._detect_via_timing,
        }

    def identify_vendor(self, methods: list = ['g_hs', 'snmp', 'dhcp', 'dns', 'tr069', 'timing']) -> dict | None:
        """
        Runs all specified detection methods, correlates the results, and returns the
        most likely vendor if the confidence exceeds a threshold.
        """
        if not self.signatures:
            logging.error("Signature database is empty. Cannot perform detection.")
            return None

        all_findings = []
        for method_name in methods:
            if method_name in self.detection_methods:
                logging.info(f"Attempting detection via {method_name}...")
                findings = self.detection_methods[method_name]()
                if findings:
                    all_findings.extend(findings)
            else:
                logging.warning(f"Detection method '{method_name}' not implemented.")

        if not all_findings:
            logging.warning("Could not identify DSLAM vendor with the specified methods.")
            return None

        vendor_scores = defaultdict(float)
        vendor_evidence = defaultdict(list)

        for finding in all_findings:
            vendor = finding['vendor']
            method = finding['method']
            certainty = finding['certainty']
            weight = self.METHOD_WEIGHTS.get(method, 0)
            score = (certainty / 100.0) * weight
            vendor_scores[vendor] += score
            vendor_evidence[vendor].append(finding)

        if not vendor_scores:
            logging.warning("No vendor matched any signature.")
            return None

        sorted_vendors = sorted(vendor_scores.items(), key=lambda item: item[1], reverse=True)

        if len(sorted_vendors) > 1:
            top_vendor, top_score = sorted_vendors[0]
            second_vendor, second_score = sorted_vendors[1]
            if top_score > 30 and (top_score - second_score) < 10:
                logging.warning(
                    f"Conflict detected: High confidence in multiple vendors. "
                    f"Top: {top_vendor} ({top_score:.2f}%) with evidence: {vendor_evidence[top_vendor]}. "
                    f"Second: {second_vendor} ({second_score:.2f}%) with evidence: {vendor_evidence[second_vendor]}."
                )

        best_vendor, best_score = sorted_vendors[0]

        if best_score < self.FINAL_CONFIDENCE_THRESHOLD:
            logging.warning(
                f"Best match '{best_vendor}' with score {best_score:.2f}% "
                f"did not meet the final confidence threshold of {self.FINAL_CONFIDENCE_THRESHOLD}%."
            )
            return None

        return {
            "primary_vendor": best_vendor,
            "overall_confidence": min(round(best_score, 2), 100.0),
            "contributing_methods": vendor_evidence[best_vendor],
            "all_results": {vendor: round(score, 2) for vendor, score in sorted_vendors}
        }

    def _detect_via_g_hs(self) -> list:
        analysis = self.ghs_analyzer.analyze_capture()
        if not analysis or 'vendor_id' not in analysis: return []

        findings = []
        analyzed_vendor_id = analysis['vendor_id']
        analyzed_vsi = analysis.get('vsi', b'').decode('ascii', errors='ignore')
        for vendor, data in self.signatures.items():
            ghs_data = data.get('ghs', {})
            for sig in ghs_data.get('signatures', []):
                certainty = 0
                if sig.get('vendor_id') == analyzed_vendor_id: certainty += self.GHS_VENDOR_ID_CERTAINTY
                for pattern in sig.get('vsi_patterns', []):
                    if pattern in analyzed_vsi: certainty += self.GHS_VSI_CERTAINTY
                if certainty > 0:
                    findings.append({"vendor": vendor, "certainty": min(certainty, 100), "method": "g_hs", "raw_data": f"VSI: {analyzed_vsi}"})
        return findings

    def _detect_via_timing(self) -> list:
        analysis = self.ghs_analyzer.analyze_capture()
        if not analysis or "handshake_duration" not in analysis: return []
        duration = analysis["handshake_duration"]

        findings = []
        for vendor, data in self.signatures.items():
            timing_sig = data.get('timing', {}).get('handshake_duration_ms', {})
            if timing_sig and timing_sig.get('min') <= duration <= timing_sig.get('max'):
                findings.append({"vendor": vendor, "certainty": 100, "method": "timing", "raw_data": f"{duration:.2f}ms"})
        return findings

    def _detect_via_snmp(self) -> list:
        """
        Detects the DSLAM vendor using SNMP by querying the sysObjectID.
        """
        sys_object_id = self.snmp_manager.get(SYSTEM_OIDS['sysObjectID'])

        if not sys_object_id:
            logging.warning("SNMP detection failed: Could not retrieve sysObjectID.")
            return []

        # The returned OID might be prefixed, so we check if our known OIDs are a substring
        for vendor, data in self.signatures.items():
            snmp_sig = data.get('snmp', {})
            if 'sysObjectID' in snmp_sig and snmp_sig['sysObjectID'] in sys_object_id:
                return [{"vendor": vendor, "certainty": 100, "method": "snmp", "raw_data": sys_object_id}]

        logging.info(f"No matching SNMP signature found for sysObjectID: {sys_object_id}")
        return []

    def _detect_via_dhcp(self) -> list:
        analysis = self.dhcp_analyzer.capture_and_analyze()
        if not analysis or 'circuit_id' not in analysis: return []
        circuit_id_str = analysis['circuit_id'].decode('ascii', errors='ignore')
        for vendor, data in self.signatures.items():
            dhcp_sig = data.get('dhcp', {})
            if 'circuit_id_pattern' in dhcp_sig and re.match(dhcp_sig['circuit_id_pattern'], circuit_id_str):
                return [{"vendor": vendor, "certainty": 100, "method": "dhcp", "raw_data": circuit_id_str}]
        return []

    def _detect_via_dns(self, target_ip: str = '8.8.8.8') -> list:
        hostname = self.dns_analyzer.get_hostname_by_ip(target_ip)
        if not hostname: return []
        findings = []
        hostname_lower = hostname.lower()
        for vendor, data in self.signatures.items():
            dns_sig = data.get('dns', {})
            certainty = 0
            if any(re.search(p, hostname_lower) for p in dns_sig.get('vendor_patterns', [])): certainty += self.DNS_VENDOR_CERTAINTY
            if any(re.search(p, hostname_lower) for p in dns_sig.get('model_patterns', [])): certainty += self.DNS_MODEL_CERTAINTY
            if certainty > 0:
                findings.append({"vendor": vendor, "certainty": certainty, "method": "dns", "raw_data": hostname})
        return findings

    def _detect_via_tr069(self) -> list:
        analysis = self.tr069_analyzer.capture_and_analyze()
        if not analysis or 'manufacturer' not in analysis: return []
        manufacturer = analysis['manufacturer']
        for vendor, data in self.signatures.items():
            tr069_sig = data.get('tr069', {})
            for pattern in tr069_sig.get('manufacturer_patterns', []):
                if re.search(pattern, manufacturer, re.IGNORECASE):
                    return [{"vendor": vendor, "certainty": 100, "method": "tr069", "raw_data": manufacturer}]
        return []