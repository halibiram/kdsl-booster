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

        Args:
            interface: The network interface to capture from (e.g., 'eth0', 'br-lan').
            duration: The duration in seconds to capture traffic.

        Returns:
            A dictionary with the parsed 'circuit_id' and 'remote_id', or None.
        """
        logging.info(f"Starting DHCP packet capture on {interface} for {duration} seconds.")
        command = (
            f"tcpdump -i {interface} -w {self.capture_file_path} "
            f"-U -W 1 -G {duration} 'udp port 67 or 68'"
        )
        stdout, stderr = self.ssh.execute_command(command)

        if stderr and "listening on" not in stderr.lower():
            logging.error(f"Error during tcpdump execution: {stderr}")
            return None
        logging.info("Packet capture completed.")

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
        """
        analysis = {}
        i = 0
        while i < len(data):
            sub_opt_code = data[i]
            # Ensure there is a length byte
            if i + 1 >= len(data):
                break
            sub_opt_len = data[i+1]

            # Ensure the full sub-option is within the data bounds
            if i + 1 + sub_opt_len >= len(data) + 1:
                break

            sub_opt_value = data[i+2 : i+2+sub_opt_len]

            if sub_opt_code == 1: # Agent Circuit ID
                analysis['circuit_id'] = sub_opt_value
            elif sub_opt_code == 2: # Agent Remote ID
                analysis['remote_id'] = sub_opt_value

            i += 2 + sub_opt_len # Move to the next sub-option

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