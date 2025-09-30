"""
This module provides the GHSHandshakeAnalyzer class, which is responsible
for capturing, parsing, and analyzing G.994.1 (G.hs) handshake protocols
used in DSL connections.

It uses tcpdump for packet capture and Scapy for parsing the captured data.
"""
import logging
from scapy.all import rdpcap

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GHSHandshakeAnalyzer:
    """
    Analyzes G.hs handshake traffic to identify DSLAM capabilities and vendor.
    """

    def __init__(self, ssh_interface):
        """
        Initializes the analyzer with an SSH interface for remote command execution.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
        """
        self.ssh = ssh_interface
        self.capture_file_path = "/tmp/ghs_capture.pcap"

    def capture_handshake(self, interface: str = 'dsl0', duration: int = 15) -> bool:
        """
        Captures DSL handshake traffic from a given interface using tcpdump.

        Args:
            interface: The network interface to capture from (e.g., 'dsl0').
            duration: The duration in seconds to capture traffic.

        Returns:
            True if capture was successful, False otherwise.
        """
        logging.info(f"Starting G.hs packet capture on {interface} for {duration} seconds.")
        # The filter 'llc' is a common way to isolate G.hs frames.
        command = (
            f"tcpdump -i {interface} -w {self.capture_file_path} "
            f"-U -W 1 -G {duration} 'llc'"
        )
        stdout, stderr = self.ssh.execute_command(command)

        if stderr and "listening on" not in stderr.lower():
            logging.error(f"Error during tcpdump execution: {stderr}")
            return False

        logging.info(f"Packet capture completed. Data saved to {self.capture_file_path} on the remote device.")
        return True

    def analyze_capture(self) -> dict:
        """
        Downloads and analyzes the captured pcap file to extract handshake details.

        Returns:
            A dictionary containing parsed G.hs messages and extracted capabilities.
        """
        logging.info(f"Downloading capture file: {self.capture_file_path}")
        local_pcap_path = "ghs_capture.pcap"
        try:
            self.ssh.sftp_get(self.capture_file_path, local_pcap_path)
            logging.info(f"Successfully downloaded {local_pcap_path}")
        except Exception as e:
            logging.error(f"Failed to download capture file: {e}")
            return {}

        try:
            packets = rdpcap(local_pcap_path)
            logging.info(f"Read {len(packets)} packets from capture file.")
        except Exception as e:
            logging.error(f"Scapy failed to read pcap file {local_pcap_path}: {e}")
            return {}

        parsed_messages = []
        full_handshake_signature = b''

        for pkt in packets:
            if 'LLC' in pkt:
                payload = bytes(pkt['LLC'].payload)
                full_handshake_signature += payload
                msg = self._parse_ghs_message(payload)
                if msg:
                    parsed_messages.append(msg)

        # For vendor identification, the initial CL message from the DSLAM is often unique
        vendor_signature = self._extract_cl_message_payload(parsed_messages)

        analysis_results = {
            "messages": parsed_messages,
            "capabilities": self._extract_capabilities(parsed_messages),
            "vendor_signature": vendor_signature
        }

        return analysis_results

    def _parse_ghs_message(self, payload: bytes) -> dict | None:
        """
        Parses a raw G.hs message payload.

        This is a simplified parser focusing on identifying message types and parameters.
        G.hs messages are complex; this parser looks for key identifiers.

        Args:
            payload: The raw bytes of the G.hs message.

        Returns:
            A dictionary with the parsed message, or None if it's not a recognized type.
        """
        # G.hs messages are typically identified by the first few bytes.
        # This is a simplified identification scheme.
        if payload.startswith(b'\x01'):
            msg_type = 'CLR' # Client Request
        elif payload.startswith(b'\x02'):
            msg_type = 'CL'  # Capabilities List (from DSLAM)
        elif payload.startswith(b'\x03'):
            msg_type = 'MS'  # Mode Select
        elif payload.startswith(b'\x04'):
            msg_type = 'ACK'
        else:
            return None # Not a message type we are parsing

        # The rest of the payload contains parameters, often in TLV format.
        # For this simulation, we'll just store the raw parameters block.
        parameters = payload[1:]

        return {"type": msg_type, "payload": payload, "parameters": parameters}

    def _extract_cl_message_payload(self, messages: list) -> bytes:
        """Finds the first CL message and returns its payload for signature matching."""
        for msg in messages:
            if msg['type'] == 'CL':
                return msg['payload']
        return b''

    def _extract_capabilities(self, messages: list) -> dict:
        """
        Extracts key capabilities from the parsed G.hs messages.
        This focuses on the 'CL' (Capabilities List) from the DSLAM.
        """
        capabilities = {}
        for msg in messages:
            if msg['type'] == 'CL':
                # This is a placeholder for a more detailed parser.
                # A real implementation would parse the TLV parameters.
                # For example, check for bits indicating VDSL2 profile support.
                if b'\x81' in msg['parameters']: # Example: Parameter for VDSL2 profiles
                    capabilities['VDSL2_Profiles'] = "Detected"
                if b'\x82' in msg['parameters']: # Example: Parameter for Vectoring
                    capabilities['Vectoring'] = "Detected"
        return capabilities