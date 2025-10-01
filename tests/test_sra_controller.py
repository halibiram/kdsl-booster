import unittest
from unittest.mock import MagicMock, patch
import time

from src.sra_controller import SRAController, SRAState
from src.keenetic_dsl_interface import DslHalBase


class TestSRAController(unittest.TestCase):
    """Unit tests for the SRAController class."""

    def setUp(self):
        """Set up a mock HAL and the SRAController for each test."""
        self.mock_hal = MagicMock(spec=DslHalBase)
        self.controller = SRAController(self.mock_hal)

        # Default mock return values
        self.mock_hal.get_line_stats.return_value = {'crc_errors': 0}
        self.mock_hal.get_snr_margin.return_value = 15.0
        self.mock_hal.control_bitswap.return_value = True
        self.mock_hal.set_snr_margin.return_value = True
        self.mock_hal.set_upstream_power_boost.return_value = True

    def test_initial_state_is_stable(self):
        """Test that the controller initializes in the STABLE state."""
        self.assertEqual(self.controller.state, SRAState.STABLE)

    def test_state_becomes_unstable_on_crc_errors(self):
        """Test that the state transitions to UNSTABLE when CRC errors exceed the threshold."""
        # Initial state check
        self.controller._update_state()
        self.assertEqual(self.controller.state, SRAState.STABLE)

        # Simulate a spike in CRC errors
        self.mock_hal.get_line_stats.return_value = {'crc_errors': self.controller.crc_error_threshold + 1}
        self.controller._update_state()

        self.assertEqual(self.controller.state, SRAState.UNSTABLE)

    def test_unstable_state_triggers_snr_increase(self):
        """Test that the UNSTABLE state leads to an increase in the SNR margin."""
        self.controller.state = SRAState.UNSTABLE
        self.controller._run_state_action()

        # Verify that set_snr_margin was called to increase the margin
        self.mock_hal.set_snr_margin.assert_called_once()
        # The new margin should be current (15.0) + step (0.5) = 15.5, sent as 155
        self.mock_hal.set_snr_margin.assert_called_with(155)

    @patch('time.time')
    def test_state_becomes_optimizing_up_when_stable_and_traffic_is_high(self, mock_time):
        """Test that the state transitions to OPTIMIZING_UP when the line is stable for long enough and traffic is high."""
        # Setup: Line has been stable for longer than the threshold
        current_time = 1000.0
        self.controller.stable_since_time = current_time - (self.controller.stable_time_for_optimization_s + 1)
        mock_time.return_value = current_time

        # Simulate high traffic
        with patch.object(self.controller, '_get_current_traffic', return_value=self.controller.traffic_threshold_mbps + 1):
            self.controller._update_state()

        self.assertEqual(self.controller.state, SRAState.OPTIMIZING_UP)

    def test_optimizing_up_state_triggers_snr_decrease(self):
        """Test that the OPTIMIZING_UP state leads to a decrease in the SNR margin."""
        self.controller.state = SRAState.OPTIMIZING_UP
        self.controller.request_rate_increase(force_retrain=False)

        # Verify that set_snr_margin was called to decrease the margin
        self.mock_hal.set_snr_margin.assert_called_once()
        # The new margin should be current (15.0) - step (0.1) = 14.9, sent as 149
        self.mock_hal.set_snr_margin.assert_called_with(149)

    @patch('time.time')
    def test_state_becomes_power_saving_when_stable_and_traffic_is_low(self, mock_time):
        """Test that the state transitions to POWER_SAVING when the line is stable and traffic is low."""
        # Setup: Line has been stable for longer than the threshold
        current_time = 1000.0
        self.controller.stable_since_time = current_time - (self.controller.stable_time_for_optimization_s + 1)
        mock_time.return_value = current_time

        # Simulate low traffic
        with patch.object(self.controller, '_get_current_traffic', return_value=self.controller.low_traffic_threshold_mbps - 1):
            self.controller._update_state()

        self.assertEqual(self.controller.state, SRAState.POWER_SAVING)

    def test_power_saving_state_triggers_snr_increase(self):
        """Test that the POWER_SAVING state leads to an increase in the SNR margin."""
        self.controller.state = SRAState.POWER_SAVING
        self.controller._run_state_action()

        self.mock_hal.set_snr_margin.assert_called_once()
        # The new margin should be current (15.0) + step (0.5) = 15.5, sent as 155
        self.mock_hal.set_snr_margin.assert_called_with(155)

    def test_manage_power_increases_boost_when_optimizing_up(self):
        """Test that power boost is increased when in the OPTIMIZING_UP state."""
        self.controller.state = SRAState.OPTIMIZING_UP
        self.controller.manage_power()

        self.mock_hal.set_upstream_power_boost.assert_called_once_with(self.controller.power_boost_step_db)
        self.assertEqual(self.controller.current_power_boost_db, self.controller.power_boost_step_db)

    def test_manage_power_decreases_boost_when_power_saving(self):
        """Test that power boost is decreased when in the POWER_SAVING state."""
        # First, set a non-zero power boost
        self.controller.current_power_boost_db = 2
        self.controller.state = SRAState.POWER_SAVING
        self.controller.manage_power()

        # The boost should decrease by the step amount
        expected_boost = 2 - self.controller.power_boost_step_db
        self.mock_hal.set_upstream_power_boost.assert_called_once_with(expected_boost)
        self.assertEqual(self.controller.current_power_boost_db, expected_boost)


if __name__ == '__main__':
    unittest.main()