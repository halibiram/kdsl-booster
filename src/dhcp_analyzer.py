"""
This module provides the DHCPAnalyzer class, responsible for capturing
and parsing DHCP packets to extract vendor-specific information from
DHCP Option 82 (Relay Agent Information).
"""
import logging
from scapy.all import rdpcap, DHCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DHCPAnalyzer:
    """
    Analyzes DHCP traffic to identify DSLAM vendor signatures in Option 82.
    """

    def __init__(self, ssh_interface):
        """
        Initializes the analyzer with an SSH interface for remote command execution.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
        """
        self.ssh = ssh_interface
        self.capture_file_path = "/tmp/dhcp_capture.pcap"

    def capture_and_analyze(self, interface: str = 'eth0', duration: int = 20) -> dict | None:
        """
        Captures DHCP traffic and analyzes it for Option 82.
        """
        logging.info(f"Starting DHCP packet capture on {interface} for {duration} seconds.")
        command = (
            f"tcpdump -i {interface} -w {self.capture_file_path} "
            f"-U -W 1 -G {duration} 'udp port 67 or 68'"
        )
        try:
            _, stderr = self.ssh.execute_command(command)
            if stderr and "listening on" not in stderr.lower() and "packets captured" not in stderr.lower():
                logging.warning(f"tcpdump for DHCP returned an error or unexpected output: {stderr.strip()}")
                # Continue to analysis, as some packets might have been captured.
        except Exception as e:
            logging.error(f"An exception occurred while executing DHCP tcpdump: {e}", exc_info=True)
            return None

        logging.info("DHCP packet capture completed.")
        return self._analyze_capture_file()

    def _analyze_capture_file(self) -> dict | None:
        """Downloads and analyzes the captured pcap file."""
        logging.info(f"Downloading DHCP capture file: {self.capture_file_path}")
        local_pcap_path = "dhcp_capture.pcap"
        try:
            self.ssh.sftp_get(self.capture_file_path, local_pcap_path)
            logging.info(f"Successfully downloaded {local_pcap_path}")
        except Exception as e:
            logging.error(f"Failed to download capture file: {e}")
            return None

        try:
            packets = rdpcap(local_pcap_path)
            logging.info(f"Read {len(packets)} packets from DHCP capture file.")
        except Exception as e:
            logging.error(f"Scapy failed to read pcap file {local_pcap_path}: {e}")
            return None

        return self._parse_dhcp_packets(packets)

    def _parse_option_82_suboptions(self, data: bytes) -> dict:
        """
        Manually parses the TLV-encoded sub-options within DHCP Option 82.
        This parser is hardened against malformed data.
        """
        analysis = {}
        i = 0
        try:
            while i < len(data):
                # Check for at least 2 bytes (Type and Length)
                if i + 1 >= len(data):
                    logging.warning("Malformed Option 82: Truncated sub-option header.")
                    break

                sub_opt_code = data[i]
                sub_opt_len = data[i+1]

                # Check if the declared length is valid
                value_start_index = i + 2
                value_end_index = value_start_index + sub_opt_len
                if value_end_index > len(data):
                    logging.warning(f"Malformed Option 82: Sub-option {sub_opt_code} has invalid length {sub_opt_len}.")
                    break

                sub_opt_value = data[value_start_index:value_end_index]

                if sub_opt_code == 1: # Agent Circuit ID
                    analysis['circuit_id'] = sub_opt_value
                elif sub_opt_code == 2: # Agent Remote ID
                    analysis['remote_id'] = sub_opt_value

                i = value_end_index # Move to the next sub-option
        except Exception as e:
            logging.error(f"An exception occurred while parsing DHCP Option 82 sub-options: {e}", exc_info=True)

        return analysis

    def _parse_dhcp_packets(self, packets) -> dict | None:
        """
        Parses a list of Scapy packets to find and extract DHCP Option 82.
        """
        for pkt in packets:
            if pkt.haslayer(DHCP):
                for opt in pkt[DHCP].options:
                    if opt[0] == 'relay_agent_information':
                        # opt[1] contains the raw bytes of the sub-options
                        analysis = self._parse_option_82_suboptions(opt[1])
                        if analysis:
                            logging.info(f"Found and parsed DHCP Option 82: {analysis}")
                            return analysis

        logging.warning("No DHCP packets with Option 82 found in capture.")
        return None