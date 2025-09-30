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
            A dictionary containing structured analysis of the G.hs handshake.
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
        for pkt in packets:
            if 'LLC' in pkt:
                payload = bytes(pkt['LLC'].payload)
                msg = self._parse_ghs_message(payload)
                if msg:
                    parsed_messages.append(msg)

        cl_message = self._extract_cl_message(parsed_messages)
        if not cl_message:
            logging.warning("No CL message found in capture.")
            return {}

        analysis_results = {
            "cl_message_payload": cl_message.get("payload"),
            "vendor_id": cl_message.get("vendor_id"),
            "vsi": cl_message.get("vsi"),
            "full_analysis": cl_message
        }

        return analysis_results

    def _parse_ghs_message(self, payload: bytes) -> dict | None:
        """
        Parses a raw G.994.1 message payload into a structured format.

        This parser identifies the message type and decodes the Non-Standard
        Information Field (NSIF) to extract the vendor ID and VSI.

        Args:
            payload: The raw bytes of the G.hs message.

        Returns:
            A dictionary with the parsed message, or None if parsing fails.
        """
        if not payload:
            return None

        msg_type_map = {1: 'CLR', 2: 'CL', 3: 'MS', 4: 'ACK'}
        msg_type = msg_type_map.get(payload[0])
        if not msg_type:
            return None

        parsed_data = {"type": msg_type, "payload": payload, "vendor_id": None, "vsi": None}

        # The NSIF parameter is identified by a marker (0x91 for CL/CLR).
        # It's a TLV (Type-Length-Value) field inside the message.
        # Let's find the marker and parse it directly.
        try:
            # Start search after the message type byte
            nsif_marker_index = payload.index(b'\x91', 1)

            # Ensure there's at least a length byte after the marker
            if nsif_marker_index + 1 < len(payload):
                param_len = payload[nsif_marker_index + 1]
                nsif_data_start = nsif_marker_index + 2

                # Ensure the full parameter data is within the payload bounds
                if nsif_data_start + param_len <= len(payload):
                    nsif_data = payload[nsif_data_start : nsif_data_start + param_len]

                    # NSIF contains: T.35 Country Code (2B), Provider Code (4B), VSI (...)
                    if len(nsif_data) >= 6:
                        vendor_id_bytes = nsif_data[2:6]
                        parsed_data["vendor_id"] = vendor_id_bytes.decode('ascii', errors='ignore')
                        parsed_data["vsi"] = nsif_data[6:] # Assign the rest of the bytes as VSI
        except ValueError:
            # This is not an error, it just means no NSIF was found.
            pass

        return parsed_data

    def _extract_cl_message(self, messages: list) -> dict | None:
        """Finds the first CL message and returns its parsed dictionary."""
        for msg in messages:
            if msg['type'] == 'CL':
                return msg
        return None