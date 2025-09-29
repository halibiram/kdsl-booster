import unittest
from unittest.mock import patch, MagicMock
from src.native_dsl_control import KeeneticNativeDSL

class TestKeeneticNativeDSL(unittest.TestCase):

    @patch('os.open')
    def test_initialization_and_chipset_info(self, mock_os_open):
        """
        Tests that the class initializes correctly and fetches chipset info.
        """
        # Arrange
        mock_os_open.return_value = 1  # Mock file descriptor

        # Act
        native_dsl = KeeneticNativeDSL()

        # Assert
        self.assertIsNotNone(native_dsl.chipset_info)
        self.assertEqual(native_dsl.chipset_info['vendor'], 'Lantiq/Econet')
        self.assertTrue(len(native_dsl.register_map) > 0)
        mock_os_open.assert_called_with('/dev/mem', os.O_RDWR | os.O_SYNC)

    @patch('os.open', side_effect=PermissionError)
    def test_initialization_no_dev_mem_permission(self, mock_os_open):
        """
        Tests that the class handles a lack of permissions gracefully.
        """
        # Act
        native_dsl = KeeneticNativeDSL()

        # Assert
        self.assertIsNone(native_dsl.mem_fd)

    def test_get_uci_config_placeholder(self):
        """
        Tests the placeholder UCI config reading method.
        """
        # Arrange
        native_dsl = KeeneticNativeDSL()

        # Act
        config = native_dsl.get_uci_config('dsl')

        # Assert
        self.assertEqual(config['profile'], '17a')

    def test_set_uci_config_placeholder(self):
        """
        Tests the placeholder UCI config writing method.
        """
        # Arrange
        native_dsl = KeeneticNativeDSL()

        # Act
        success = native_dsl.set_uci_config('dsl', {'profile': '35b'})

        # Assert
        self.assertTrue(success)

    @patch('mmap.mmap')
    @patch('os.open')
    def test_read_dsl_register(self, mock_os_open, mock_mmap):
        """
        Tests the logic for reading a value from a register via /dev/mem.
        """
        # Arrange
        mock_os_open.return_value = 1

        # Create a mock memory map
        mock_map_instance = MagicMock()
        mock_mmap.return_value = mock_map_instance

        # Simulate reading the 32-bit integer 0xDEADBEEF
        mock_map_instance.read.return_value = b'\xef\xbe\xad\xde'

        with patch('struct.unpack_from', return_value=(0xDEADBEEF,)):
            native_dsl = KeeneticNativeDSL()

            # Act
            value = native_dsl.read_dsl_register('FE_DMA_GLO_CFG')

            # Assert
            self.assertEqual(value, 0xDEADBEEF)
            mock_mmap.assert_called_once()
            mock_map_instance.close.assert_called_once()

    @patch('mmap.mmap')
    @patch('os.open')
    def test_manipulate_dsl_registers(self, mock_os_open, mock_mmap):
        """
        Tests the logic for writing a value to a register via /dev/mem.
        """
        # Arrange
        mock_os_open.return_value = 1

        mock_map_instance = MagicMock()
        mock_mmap.return_value = mock_map_instance

        with patch('struct.pack_into') as mock_pack_into:
            native_dsl = KeeneticNativeDSL()
            registers_to_write = {'PTM_CTRL': 0x12345678}

            # Act
            success = native_dsl.manipulate_dsl_registers(registers_to_write)

            # Assert
            self.assertTrue(success)
            mock_mmap.assert_called_once()
            mock_pack_into.assert_called_once()
            # Check that the correct value was packed
            args, _ = mock_pack_into.call_args
            self.assertEqual(args[2], 0x12345678)
            mock_map_instance.close.assert_called_once()

    def test_manipulate_unknown_register(self):
        """
        Tests that writing to an unknown register fails gracefully.
        """
        # Arrange
        native_dsl = KeeneticNativeDSL()

        # Act
        success = native_dsl.manipulate_dsl_registers({'UNKNOWN_REG': 0x1})

        # Assert
        self.assertFalse(success)

if __name__ == '__main__':
    unittest.main()