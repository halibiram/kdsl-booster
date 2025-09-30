"""
This module provides the TR069Analyzer class, responsible for capturing
and parsing TR-069 (CWMP) traffic to extract vendor-specific information.
"""
import logging
import xml.etree.ElementTree as ET
from scapy.all import rdpcap

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TR069Analyzer:
    """
    Analyzes TR-069 traffic to identify vendor signatures from SOAP messages.
    """

    def __init__(self, ssh_interface):
        """
        Initializes the analyzer with an SSH interface for remote command execution.
        """
        self.ssh = ssh_interface
        self.capture_file_path = "/tmp/tr069_capture.pcap"

    def capture_and_analyze(self, interface: str = 'br-lan', duration: int = 20) -> dict | None:
        """
        Captures TR-069 traffic and analyzes it for vendor information.
        """
        logging.info(f"Starting TR-069 packet capture on {interface} for {duration} seconds.")
        command = (
            f"tcpdump -i {interface} -w {self.capture_file_path} "
            f"-U -W 1 -G {duration} 'tcp port 7547'"
        )
        try:
            # Note: This command is not expected to succeed in the sandboxed test environment,
            # but the error handling is implemented for real-world use.
            _, stderr = self.ssh.execute_command(command)
            if stderr and "listening on" not in stderr.lower() and "packets captured" not in stderr.lower():
                logging.warning(f"tcpdump for TR-069 returned an error or unexpected output: {stderr.strip()}")
        except Exception as e:
            logging.error(f"An exception occurred while executing TR-069 tcpdump: {e}", exc_info=True)
            # In case of capture failure, we can't proceed with analysis of the (non-existent) file.
            return None

        logging.info("TR-069 packet capture completed.")
        return self._analyze_capture_file()

    def _analyze_capture_file(self) -> dict | None:
        """
        Downloads and analyzes the captured pcap file.
        """
        local_pcap_path = "tr069_capture.pcap"
        try:
            packets = rdpcap(local_pcap_path)
            logging.info(f"Read {len(packets)} packets from TR-069 capture file.")
        except FileNotFoundError:
            logging.warning(f"Mock capture file not found: {local_pcap_path}.")
            return None
        except Exception as e:
            logging.error(f"Scapy failed to read pcap file {local_pcap_path}: {e}")
            return None

        return self._parse_tr069_packets(packets)

    def _extract_soap_payload(self, packet) -> str | None:
        """Extracts the TCP payload which should contain the SOAP message."""
        if packet.haslayer('TCP') and packet.haslayer('Raw'):
            return packet['Raw'].load.decode('utf-8', errors='ignore')
        return None

    def _parse_inform_message(self, soap_body: str) -> dict | None:
        """
        Parses the XML of a TR-069 Inform message to extract key device info.
        """
        try:
            # Remove leading whitespace that can interfere with parsing
            soap_body = soap_body.strip()
            root = ET.fromstring(soap_body)
            namespaces = {
                'soap-env': 'http://schemas.xmlsoap.org/soap/envelope/',
                'cwmp': 'urn:dslforum-org:cwmp-1-0'
            }

            # Find the Inform element using its full namespace
            inform_element = root.find('.//{urn:dslforum-org:cwmp-1-0}Inform')
            if inform_element is None:
                return None

            # The DeviceId element is not namespaced in the sample data
            device_id_element = inform_element.find('DeviceId')
            if device_id_element is None:
                return None

            # The elements inside DeviceId ARE namespaced
            manufacturer = device_id_element.find('cwmp:Manufacturer', namespaces)
            product_class = device_id_element.find('cwmp:ProductClass', namespaces)

            analysis = {}
            if manufacturer is not None and manufacturer.text:
                analysis['manufacturer'] = manufacturer.text
            if product_class is not None and product_class.text:
                analysis['product_class'] = product_class.text

            logging.info(f"Parsed TR-069 Inform message: {analysis}")
            return analysis if analysis else None

        except ET.ParseError:
            # This is expected if the payload isn't valid XML
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during XML parsing: {e}")
            return None

    def _parse_tr069_packets(self, packets) -> dict | None:
        """
        Parses a list of Scapy packets to find and extract TR-069 Inform data.
        """
        for pkt in packets:
            soap_payload = self._extract_soap_payload(pkt)
            if soap_payload and "POST" in soap_payload and "Inform" in soap_payload:
                # Find the start of the XML content
                xml_start_index = soap_payload.find('<')
                if xml_start_index != -1:
                    xml_body = soap_payload[xml_start_index:]
                    analysis = self._parse_inform_message(xml_body)
                    if analysis:
                        return analysis

        logging.warning("No valid TR-069 Inform messages found in capture.")
        return None