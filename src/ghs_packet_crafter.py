import logging
from scapy.all import Packet, ByteField, FieldLenField, StrLenField, PacketListField, NoPayload

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NPar(Packet):
    """
    Represents a Name/Parameter (NPar) field, a basic TLV-like structure.
    """
    name = "NPar"
    fields_desc = [
        ByteField("npar_id", 0),
        FieldLenField("npar_len", None, length_of="npar_payload", fmt="B"),
        StrLenField("npar_payload", b"", length_from=lambda p: p.npar_len)
    ]

class SPar(Packet):
    """
    Represents a Standard Parameter (SPar) field. This implementation uses a
    manual dissection pattern, which is the robust way to handle a list of
    packets where the length is defined in bytes.
    """
    name = "SPar"
    fields_desc = [
        ByteField("spar_id", 0),
        # The length of the raw bytes of the NPar list
        FieldLenField("spar_len", None, length_of="raw_npars", fmt="!H"),
        # A field to hold the raw bytes of the NPar list
        StrLenField("raw_npars", b"", length_from=lambda p: p.spar_len),
    ]

    def post_dissect(self, s):
        """
        After dissecting the raw bytes, parse them into a list of NPar objects.
        This list is stored in a new attribute, `npar_list`.
        """
        self.npar_list = []
        data = self.raw_npars
        while data:
            npar = NPar(data)
            self.npar_list.append(npar)
            if isinstance(npar.payload, NoPayload):
                break
            data = npar.payload.load
        return s

class GHS_Message(Packet):
    """
    Represents a top-level G.hs message.
    """
    name = "G.hs Message"
    fields_desc = [
        ByteField("sync_flag", 0x00),
        ByteField("message_type", 0),
        PacketListField("spar_list", [], SPar)
    ]

def craft_fake_cl_message(
    vendor_id: bytes = b'KTC_FAKE',
    profile_35b: bool = True,
    force_vectoring: bool = True
) -> bytes:
    """
    High-level function to craft a fake G.hs Capabilities List (CL) message.
    This version uses the robust manual dissection pattern.

    Args:
        vendor_id: A byte string for the fake vendor ID.
        profile_35b: If True, advertises support for VDSL2 profile 35b.
        force_vectoring: If True, advertises support for G.vector (vectoring).

    Returns:
        The raw bytes of the crafted G.hs message.
    """
    logging.info(f"Crafting fake CL message: 35b={profile_35b}, Vectoring={force_vectoring}")

    npar_list = []
    if profile_35b:
        npar_list.append(NPar(npar_id=2, npar_payload=b'\x80'))
        logging.info("Injecting VDSL2 Profile 35b capability.")
    if force_vectoring:
        npar_list.append(NPar(npar_id=3, npar_payload=b'\x01'))
        logging.info("Injecting G.vector capability.")
    if vendor_id:
        npar_list.append(NPar(npar_id=1, npar_payload=vendor_id))
        logging.info(f"Injecting Vendor ID: {vendor_id.decode(errors='ignore')}")

    # Manually build the NPar list into a raw byte string
    raw_npars_bytes = b"".join(bytes(n) for n in npar_list)

    # Instantiate SPar using the 'raw_npars' field, which is in fields_desc
    spar_container = SPar(spar_id=2, raw_npars=raw_npars_bytes)

    ghs_pkt = GHS_Message(message_type=2, spar_list=[spar_container])
    return bytes(ghs_pkt)

if __name__ == '__main__':
    # --- Example of crafting a fake CL message ---
    print("--- Example: Crafting a fake capabilities message ---")
    fake_cl_packet = craft_fake_cl_message(
        vendor_id=b'ACME_MODEM',
        profile_35b=True,
        force_vectoring=True
    )

    print("\nRaw packet bytes:")
    print(fake_cl_packet.hex())

    # --- Verify the structure ---
    print("\nScapy dissection of the crafted packet:")
    decoded_pkt = GHS_Message(fake_cl_packet)
    # To see the manually dissected list:
    if decoded_pkt.spar_list:
        print("\nManually dissected NPars:")
        for npar in decoded_pkt.spar_list[0].npar_list:
            npar.show()
    else:
        decoded_pkt.show()