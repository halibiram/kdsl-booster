import unittest
import struct
from src.ghs_protocol import GHSHandshakeManipulator, CAPABILITY_BITMASKS, GHS_HEADER

class TestGHSHandshakeManipulator(unittest.TestCase):

    def setUp(self):
        """Set up a new GHSHandshakeManipulator instance for each test."""
        self.manipulator = GHSHandshakeManipulator()

    def test_parse_ghs_packet(self):
        """
        Tests that a packet with a known capability bitmask is parsed correctly.
        """
        # Arrange: Packet advertising VDSL2 profile 17a (0x0040) and G.INP (0x4000)
        capability_mask = CAPABILITY_BITMASKS['vdsl2_profile_17a'] | CAPABILITY_BITMASKS['retransmission']
        test_packet = GHS_HEADER + struct.pack('>H', capability_mask)

        # Act
        parsed_caps = self.manipulator.parse_ghs_packet(test_packet)

        # Assert
        self.assertTrue(parsed_caps.get('vdsl2_profile_17a'))
        self.assertTrue(parsed_caps.get('retransmission'))
        self.assertIsNone(parsed_caps.get('vdsl2_profile_35b'))
        self.assertIsNone(parsed_caps.get('g_vector_support'))

    def test_build_ghs_packet(self):
        """
        Tests that a packet is built correctly from a dictionary of capabilities.
        """
        # Arrange
        capabilities_to_build = {
            'vdsl2_profile_35b': True,
            'g_vector_support': True,
            'vdsl2_profile_17a': False # Should be ignored
        }

        # Expected bitmask: 0x0100 (35b) | 0x1000 (g.vector) = 0x1100
        expected_mask = CAPABILITY_BITMASKS['vdsl2_profile_35b'] | CAPABILITY_BITMASKS['g_vector_support']
        expected_packet = GHS_HEADER + struct.pack('>H', expected_mask)

        # Act
        built_packet = self.manipulator.build_ghs_packet(capabilities_to_build)

        # Assert
        self.assertEqual(built_packet, expected_packet)

    def test_inject_profile_support(self):
        """
        Tests the creation of a packet advertising a specific set of profiles.
        """
        # Arrange
        profiles_to_inject = ['vdsl2_profile_17a', 'vdsl2_profile_35b']

        # Expected bitmask: 0x0040 (17a) | 0x0100 (35b) = 0x0140
        expected_mask = CAPABILITY_BITMASKS['vdsl2_profile_17a'] | CAPABILITY_BITMASKS['vdsl2_profile_35b']
        expected_packet = GHS_HEADER + struct.pack('>H', expected_mask)

        # Act
        generated_packet = self.manipulator.inject_profile_support(profiles_to_inject)

        # Assert
        self.assertEqual(generated_packet, expected_packet)

    def test_intercept_capability_exchange(self):
        """
        Tests the full interception and modification workflow.
        """
        # Arrange: Original packet only supports 17a
        original_mask = CAPABILITY_BITMASKS['vdsl2_profile_17a']
        original_packet = GHS_HEADER + struct.pack('>H', original_mask)

        # We want to inject support for 35b and vectoring
        capabilities_to_inject = ['vdsl2_profile_35b', 'g_vector_support']

        # Expected final mask should have all three bits set
        expected_mask = (CAPABILITY_BITMASKS['vdsl2_profile_17a'] |
                         CAPABILITY_BITMASKS['vdsl2_profile_35b'] |
                         CAPABILITY_BITMASKS['g_vector_support'])
        expected_packet = GHS_HEADER + struct.pack('>H', expected_mask)

        # Act
        modified_packet = self.manipulator.intercept_capability_exchange(
            original_packet,
            capabilities_to_inject
        )

        # Assert
        self.assertEqual(modified_packet, expected_packet)

if __name__ == '__main__':
    unittest.main()