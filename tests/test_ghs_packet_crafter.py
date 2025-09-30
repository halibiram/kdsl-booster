import unittest
from scapy.all import raw

from src.ghs_packet_crafter import craft_fake_cl_message, GHS_Message, NPar

class TestGHSPacketCrafter(unittest.TestCase):
    """
    Unit tests for the G.hs packet crafting library. These tests have been
    updated to validate the corrected logic where all parameters are grouped
    into a single SPar container.
    """

    def test_craft_default_fake_cl_message(self):
        """
        Tests a default CL message with all capabilities enabled.
        It should contain one SPar with three NPars.
        """
        packet_bytes = craft_fake_cl_message(
            vendor_id=b'TEST',
            profile_35b=True,
            force_vectoring=True
        )
        decoded_pkt = GHS_Message(packet_bytes)

        self.assertEqual(len(decoded_pkt.spar_list), 1, "Should contain exactly one SPar")

        spar = decoded_pkt.spar_list[0]
        self.assertEqual(spar.spar_id, 2, "SPar ID should be 2 (non-standard)")
        self.assertEqual(len(spar.npar_list), 3, "SPar should contain three NPars")

        npar_payloads = {n.npar_id: n.npar_payload for n in spar.npar_list}
        self.assertIn(1, npar_payloads)
        self.assertEqual(npar_payloads[1], b'TEST')
        self.assertIn(2, npar_payloads)
        self.assertEqual(npar_payloads[2], b'\x80')
        self.assertIn(3, npar_payloads)
        self.assertEqual(npar_payloads[3], b'\x01')

    def test_craft_cl_message_no_vectoring(self):
        """
        Tests that disabling vectoring correctly produces two NPars (profile and vendor).
        """
        packet_bytes = craft_fake_cl_message(
            profile_35b=True,
            force_vectoring=False
        )
        decoded_pkt = GHS_Message(packet_bytes)
        spar = decoded_pkt.spar_list[0]

        self.assertEqual(len(spar.npar_list), 2, "SPar should contain two NPars")
        npar_ids = {n.npar_id for n in spar.npar_list}
        self.assertNotIn(3, npar_ids, "Vectoring NPar should be omitted")
        self.assertIn(2, npar_ids)
        self.assertIn(1, npar_ids)

    def test_craft_cl_message_no_35b(self):
        """
        Tests that disabling profile 35b correctly produces two NPars (vectoring and vendor).
        """
        packet_bytes = craft_fake_cl_message(
            profile_35b=False,
            force_vectoring=True
        )
        decoded_pkt = GHS_Message(packet_bytes)
        spar = decoded_pkt.spar_list[0]

        self.assertEqual(len(spar.npar_list), 2, "SPar should contain two NPars")
        npar_ids = {n.npar_id for n in spar.npar_list}
        self.assertNotIn(2, npar_ids, "Profile 35b NPar should be omitted")
        self.assertIn(3, npar_ids)
        self.assertIn(1, npar_ids)

    def test_packet_byte_level_correctness(self):
        """
        Performs a byte-level check of a known packet structure to ensure
        the crafter generates the exact bytes expected.
        """
        # Expected structure: Non-standard SPar (ID 2) with one NPar for profile 35b
        expected_bytes = b'\x00\x02\x02\x00\x03\x02\x01\x80'

        crafted_bytes = craft_fake_cl_message(
            vendor_id=None,
            profile_35b=True,
            force_vectoring=False
        )

        self.assertEqual(crafted_bytes, expected_bytes)

        # Decode for programmatic verification
        decoded_pkt = GHS_Message(crafted_bytes)
        self.assertEqual(decoded_pkt.spar_list[0].spar_id, 2)
        self.assertEqual(len(decoded_pkt.spar_list[0].npar_list), 1)
        self.assertEqual(decoded_pkt.spar_list[0].npar_list[0].npar_id, 2)
        self.assertEqual(decoded_pkt.spar_list[0].npar_list[0].npar_payload, b'\x80')

if __name__ == '__main__':
    unittest.main()