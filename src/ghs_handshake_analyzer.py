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
        """
        self.ssh = ssh_interface
        self.capture_file_path = "/tmp/ghs_capture.pcap"

    def capture_handshake(self, interface: str = 'dsl0', duration: int = 15) -> bool:
        """
        Captures DSL handshake traffic from a given interface using tcpdump.
        """
        logging.info(f"Starting G.hs packet capture on {interface} for {duration} seconds.")
        command = (
            f"tcpdump -i {interface} -w {self.capture_file_path} "
            f"-U -W 1 -G {duration} 'llc'"
        )
        try:
            _, stderr = self.ssh.execute_command(command)
            # tcpdump logs its status to stderr, so we check for common success messages.
            if stderr and "listening on" not in stderr.lower() and "packets captured" not in stderr.lower():
                logging.warning(f"tcpdump for G.hs returned an error or unexpected output: {stderr.strip()}")
                return False
        except Exception as e:
            logging.error(f"An exception occurred while executing G.hs tcpdump: {e}", exc_info=True)
            return False

        logging.info("G.hs packet capture completed.")
        return True

    def analyze_capture(self) -> dict:
        """
        Downloads and analyzes the captured pcap file to extract handshake details.
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

        ghs_packets = [p for p in packets if 'LLC' in p]
        if not ghs_packets:
            logging.warning("No G.hs (LLC) packets found in capture.")
            return {}

        # Calculate handshake duration
        first_packet_time = ghs_packets[0].time
        last_packet_time = ghs_packets[-1].time
        duration_seconds = float(last_packet_time - first_packet_time)
        handshake_duration_ms = duration_seconds * 1000
        logging.info(f"Calculated handshake duration: {handshake_duration_ms:.2f} ms")

        parsed_messages = []
        for pkt in ghs_packets:
            payload = bytes(pkt['LLC'].payload)
            msg = self._parse_ghs_message(payload)
            if msg:
                parsed_messages.append(msg)

        cl_message = self._extract_cl_message(parsed_messages)
        analysis_results = {"handshake_duration": handshake_duration_ms}

        if cl_message:
            analysis_results.update({
                "cl_message_payload": cl_message.get("payload"),
                "vendor_id": cl_message.get("vendor_id"),
                "vsi": cl_message.get("vsi"),
                "vdsl2_profiles_bitmap": cl_message.get("vdsl2_profiles_bitmap"),
                "g_vector_bitmap": cl_message.get("g_vector_bitmap"),
                "bonding_bitmap": cl_message.get("bonding_bitmap"),
                "band_plan_id": cl_message.get("band_plan_id"),
                "g_inp_bitmap": cl_message.get("g_inp_bitmap"),
                "psd_mask_id": cl_message.get("psd_mask_id"),
                "full_analysis": cl_message
            })
        else:
            logging.warning("No CL message found in G.hs packets.")

        return analysis_results

    def _parse_ghs_message(self, payload: bytes) -> dict | None:
        """
        Parses a raw G.994.1 message payload into a structured format.
        This has been hardened against malformed payloads.
        """
        if not payload: return None
        msg_type_map = {1: 'CLR', 2: 'CL', 3: 'MS', 4: 'ACK'}
        msg_type = msg_type_map.get(payload[0])
        if not msg_type: return None

        parsed_data = {
            "type": msg_type, "payload": payload, "vendor_id": None, "vsi": None,
            "vdsl2_profiles_bitmap": None, "g_vector_bitmap": None, "bonding_bitmap": None,
            "band_plan_id": None, "g_inp_bitmap": None, "psd_mask_id": None
        }
        try:
            i = 1  # Start after message type
            bonding_bitmap = 0
            while i < len(payload):
                # A simplified but more robust TLV parser for SIF.
                # Every parameter should have an ID (Type) and a Length.
                if i + 1 >= len(payload):
                    break # Not enough bytes for a full TLV

                param_id = payload[i]
                param_len = payload[i+1]

                # Ensure the full parameter is within the payload bounds
                if i + 2 + param_len > len(payload):
                    break # Malformed parameter, stop parsing

                data_start_index = i + 2

                # VDSL2 Profiles (ID 0x83)
                if param_id == 0x83 and param_len >= 2:
                    bitmap_val = int.from_bytes(payload[data_start_index:data_start_index + 2], 'big')
                    parsed_data["vdsl2_profiles_bitmap"] = bitmap_val
                # VDSL2 Band Plan (ID 0x84)
                elif param_id == 0x84 and param_len >= 1:
                    parsed_data["band_plan_id"] = payload[data_start_index]
                # VDSL2 PSD Mask (ID 0x85)
                elif param_id == 0x85 and param_len >= 1:
                    parsed_data["psd_mask_id"] = payload[data_start_index]
                # G.vector/G.993.5 Support (ID 0x86)
                elif param_id == 0x86 and param_len >= 1:
                    parsed_data["g_vector_bitmap"] = payload[data_start_index]
                # G.998.1 ATM-based Bonding (ID 0xA0)
                elif param_id == 0xA0:
                    bonding_bitmap |= (1 << 0)
                # G.998.2 Ethernet-based Bonding (ID 0xA1)
                elif param_id == 0xA1:
                    bonding_bitmap |= (1 << 1)
                # G.998.4 G.inp/Retransmission (ID 0xB0)
                elif param_id == 0xB0 and param_len >= 1:
                    parsed_data["g_inp_bitmap"] = payload[data_start_index]
                # --- NSIF Parameter Parsing ---
                elif param_id == 0x91 and param_len >= 6:
                    nsif_data = payload[data_start_index : data_start_index + param_len]
                    parsed_data["vendor_id"] = nsif_data[2:6].decode('ascii', errors='ignore')
                    parsed_data["vsi"] = nsif_data[6:]

                # Move to the next parameter using the length byte
                i += 2 + param_len

            if bonding_bitmap > 0:
                parsed_data["bonding_bitmap"] = bonding_bitmap

        except Exception as e:
            logging.warning(f"Unexpected error while parsing G.hs message: {e}")

        return parsed_data

    def _extract_cl_message(self, messages: list) -> dict | None:
        """Finds the first CL message and returns its parsed dictionary."""
        for msg in messages:
            if msg['type'] == 'CL':
                return msg
        return None