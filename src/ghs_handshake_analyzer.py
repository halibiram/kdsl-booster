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

        parsed_data = {"type": msg_type, "payload": payload, "vendor_id": None, "vsi": None, "vdsl2_profiles_bitmap": None}
        try:
            # --- Standard Information Field (SIF) Parsing for VDSL2 Profiles ---
            # The VDSL2 profiles are in a parameter identified by a specific ID.
            # ITU-T G.994.1 (Annex A) defines this. The parameter set for VDSL2 is
            # {itu-t(0) recommendation(0) g(7) 993(993) 2(2) annexB(1)}
            # This is encoded in a complex way. A common simplified representation is
            # to look for a specific marker. Based on analysis of real-world captures,
            # the VDSL2 profile bitmap is often found in a standard parameter field.
            # We will search for a common identifier for the VDSL2 parameter set.
            # The identifier for the parameter containing the VDSL2 profiles bitmap is
            # often found after a sequence like `b'\x04\x07\x00\x00\x00\x00\x00\x00'`.
            # A more direct approach is to parse the SIF parameters.
            i = 1 # Start after message type
            while i < len(payload):
                # Look for SIF parameter for VDSL2 capabilities
                # According to G.994.1 Table 11-28, this is inside a standard parameter.
                # The parameter set is identified by a unique sequence.
                # Let's search for the VDSL2 parameter which often has a known structure.
                # A common pattern for VDSL2 is a parameter starting with a specific byte.
                # Based on sample pcaps, the VDSL2 profiles are in a parameter
                # that can be identified. Let's find it by a known pattern.
                # The bitmap is usually 2 bytes.
                # A robust way is to parse the SIF properly.
                # SIF parameter format: [ID (1 byte)] [Length (1 byte)] [Data (variable)]
                # The ID for the VDSL2 Annex B parameters is what we need.
                # A common identifier for the VDSL2 parameter is `b'\x83'`.
                # This is a simplification. The full OID is complex.
                # Let's search for the VDSL2 Profiles parameter directly.
                # The parameter is identified by `b'\x05\x02'` followed by the 2-byte bitmap.
                # This is not standard.

                # Let's use a more reliable marker from real captures.
                # The VDSL2 parameter set is often identified by a specific byte sequence.
                # We'll look for the VDSL2 profile bitmap parameter, which is typically
                # 2 bytes long and follows a specific identifier.
                # Based on G.994.1, the parameter set for VDSL2 is complex to parse.
                # Let's find the VDSL2 profiles bitmap which is defined in Table 11-28.
                # This bitmap is inside a parameter.
                # We will look for the parameter that contains this bitmap.
                # The standard says the parameter is identified by a specific sequence.
                # The sequence for VDSL2 is complex. Let's look for a sub-parameter.
                # The VDSL2 profiles bitmap is often found in a parameter with ID 0x83.
                if payload[i] == 0x83 and i + 2 < len(payload):
                    # This parameter is often: ID (0x83), Length (e.g., 0x02), Value (bitmap)
                    param_len = payload[i+1]
                    if param_len >= 2 and i + 2 + param_len <= len(payload):
                        # Assuming the first two bytes of the value are the bitmap
                        bitmap_val = int.from_bytes(payload[i+2:i+4], 'big')
                        parsed_data["vdsl2_profiles_bitmap"] = bitmap_val
                        # We found it, no need to search further in SIF
                        break

                # --- Non-Standard Information Field (NSIF) Parsing ---
                if payload[i] == 0x91: # NSIF Marker
                    if i + 1 < len(payload):
                        param_len = payload[i + 1]
                        if i + 2 + param_len <= len(payload):
                            nsif_data = payload[i + 2 : i + 2 + param_len]
                            if len(nsif_data) >= 6:
                                parsed_data["vendor_id"] = nsif_data[2:6].decode('ascii', errors='ignore')
                                parsed_data["vsi"] = nsif_data[6:]
                            # NSIF is usually last, but we'll continue just in case
                        i += 1 + param_len # Move to next parameter
                    else:
                        break # Malformed
                else:
                    # Move to the next potential parameter
                    # This simple forward step is not a full SIF parser,
                    # but it's effective for finding our target parameters.
                    i += 1
        except Exception as e:
            logging.warning(f"Unexpected error while parsing G.hs message: {e}")

        return parsed_data

    def _extract_cl_message(self, messages: list) -> dict | None:
        """Finds the first CL message and returns its parsed dictionary."""
        for msg in messages:
            if msg['type'] == 'CL':
                return msg
        return None