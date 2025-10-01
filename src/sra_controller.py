import time
import logging
from enum import Enum
from src.keenetic_dsl_interface import DslHalBase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SRAState(Enum):
    """Represents the operational state of the SRA controller."""
    STABLE = "Stable"
    UNSTABLE = "Unstable"
    OPTIMIZING_UP = "Optimizing for Higher Rate"
    OPTIMIZING_DOWN = "Optimizing for Lower Rate"
    POWER_SAVING = "Power Saving"


class SRAController:
    """
    Manages Seamless Rate Adaptation (SRA) by monitoring line conditions
    and making intelligent adjustments to maintain an optimal balance between
    performance, stability, and power consumption.
    """

    def __init__(self, hal: DslHalBase, traffic_monitor=None):
        """
        Initializes the SRA Controller.

        Args:
            hal: An instance of a DslHalBase implementation for hardware interaction.
            traffic_monitor: An optional utility to monitor network traffic volume.
        """
        self.hal = hal
        self.traffic_monitor = traffic_monitor
        self.state = SRAState.STABLE
        self.is_running = False
        self.last_crc_errors = 0
        self.stable_since_time = time.time()
        self.last_check_time = time.time()
        self.current_power_boost_db = 0

        # --- SRA Tuning Parameters ---
        self.monitoring_interval_s = 10
        self.crc_error_threshold = 10  # New errors per interval to be considered unstable
        self.snr_increase_step_db = 0.5  # How much to increase SNR when unstable
        self.snr_decrease_step_db = 0.1  # How much to decrease SNR when stable
        self.power_boost_step_db = 1     # How much to adjust power in each step
        self.max_power_boost_db = 5      # The maximum allowed power boost
        self.stable_time_for_optimization_s = 60  # How long to be stable before trying to optimize
        self.traffic_threshold_mbps = 50 # Traffic volume to trigger rate increase
        self.low_traffic_threshold_mbps = 5 # Traffic volume to trigger power saving

    def _update_state(self):
        """
        Analyzes line statistics and traffic to determine the current state of the line.
        This is the core decision-making logic of the controller.
        """
        current_stats = self.hal.get_line_stats()
        if not current_stats:
            logging.warning("Could not retrieve line stats. Assuming UNSTABLE.")
            self.state = SRAState.UNSTABLE
            return

        current_crc_errors = current_stats.get('crc_errors', 0)
        new_errors = current_crc_errors - self.last_crc_errors

        if new_errors > self.crc_error_threshold:
            logging.warning(f"Line has become unstable with {new_errors} new CRC errors.")
            self.state = SRAState.UNSTABLE
            self.stable_since_time = time.time() # Reset stable timer
        else:
            if self.state == SRAState.UNSTABLE:
                logging.info("Line has stabilized.")
                self.stable_since_time = time.time()

            time_stable = time.time() - self.stable_since_time
            current_traffic = self._get_current_traffic()

            if time_stable > self.stable_time_for_optimization_s:
                if current_traffic > self.traffic_threshold_mbps:
                    self.state = SRAState.OPTIMIZING_UP
                elif current_traffic < self.low_traffic_threshold_mbps:
                    self.state = SRAState.POWER_SAVING
                else:
                    self.state = SRAState.STABLE # Stable but no need to change rate
            else:
                self.state = SRAState.STABLE

        self.last_crc_errors = current_crc_errors

    def _get_current_traffic(self) -> float:
        """Gets the current traffic volume in Mbps. Returns a simulated value if no monitor is available."""
        if self.traffic_monitor:
            return self.traffic_monitor.get_traffic_mbps()
        # Simulate traffic fluctuating for demonstration purposes
        return (50 * (time.time() % 60) / 60) + 10 # Simulate traffic between 10 and 60 Mbps

    def _run_state_action(self):
        """
        Executes actions based on the current state of the controller.
        """
        # Manage bit-swap and power based on the current state.
        if self.state in [SRAState.STABLE, SRAState.OPTIMIZING_UP, SRAState.POWER_SAVING]:
            self.manage_bitswap()
            self.manage_power()

        if self.state == SRAState.UNSTABLE:
            self.stabilize_line()
        elif self.state == SRAState.OPTIMIZING_UP:
            self.request_rate_increase(force_retrain=True)
        elif self.state == SRAState.POWER_SAVING:
            self.request_rate_decrease()
        elif self.state == SRAState.STABLE:
            logging.info("Line is stable, no action required. Monitoring...")

    def manage_bitswap(self):
        """
        Ensures bit-swap is enabled, which is essential for SRA.
        In more advanced scenarios, this could be disabled strategically
        during a full retrain, but for most SRA operations, it should be on.
        """
        logging.info("Verifying that bit-swap is enabled for SRA operations.")
        try:
            # This is a "fire-and-forget" call to ensure the state is correct.
            self.hal.control_bitswap(enabled=True)
        except NotImplementedError:
            logging.warning("Bit-swap control is not supported by the current HAL. SRA may not function correctly.")

    def manage_power(self):
        """
        Adjusts the upstream power boost based on the current operational state.
        """
        target_boost = self.current_power_boost_db

        if self.state == SRAState.OPTIMIZING_UP:
            target_boost = min(self.max_power_boost_db, self.current_power_boost_db + self.power_boost_step_db)
            logging.info(f"Increasing power boost to {target_boost} dB to support higher rate.")
        elif self.state == SRAState.POWER_SAVING:
            target_boost = max(0, self.current_power_boost_db - self.power_boost_step_db)
            logging.info(f"Reducing power boost to {target_boost} dB to conserve power.")

        if target_boost != self.current_power_boost_db:
            try:
                self.hal.set_upstream_power_boost(target_boost)
                self.current_power_boost_db = target_boost
            except NotImplementedError:
                logging.warning("Upstream power boost control is not supported by the current HAL.")

    def stabilize_line(self):
        """
        Action taken when the line is unstable. The primary goal is to
        increase the SNR margin to regain stability.
        """
        current_snr = self.hal.get_snr_margin()
        if current_snr is not None:
            target_snr = current_snr + self.snr_increase_step_db
            logging.info(f"Stabilizing line: Increasing SNR margin to {target_snr:.1f} dB.")
            self.hal.set_snr_margin(int(target_snr * 10))

    def request_rate_increase(self, force_retrain: bool = False):
        """
        Action taken when the line is stable and traffic is high.
        Cautiously reduces the SNR margin to probe for higher performance.

        Args:
            force_retrain: If True, will trigger a fast retrain after adjusting SNR.
        """
        current_snr = self.hal.get_snr_margin()
        if current_snr is not None:
            target_snr = current_snr - self.snr_decrease_step_db
            logging.info(f"High traffic detected. Probing for higher rate by reducing SNR to {target_snr:.1f} dB.")
            success = self.hal.set_snr_margin(int(target_snr * 10))

            if success and force_retrain:
                try:
                    logging.info("Forcing line renegotiation to realize rate increase faster.")
                    self.hal.force_renegotiation()
                except NotImplementedError:
                    logging.warning("force_renegotiation is not supported by the current HAL. Skipping.")

    def request_rate_decrease(self):
        """
        Action taken when the line is stable and traffic is low.
        Increases SNR margin to build a stability buffer and potentially save power.
        """
        current_snr = self.hal.get_snr_margin()
        if current_snr is not None:
            target_snr = current_snr + self.snr_increase_step_db
            logging.info(f"Low traffic detected. Increasing SNR margin to {target_snr:.1f} dB for stability and power saving.")
            self.hal.set_snr_margin(int(target_snr * 10))

    def start(self, duration_s: int):
        """
        Starts the main control loop of the SRA controller.

        Args:
            duration_s: The total time to run the controller in seconds.
        """
        logging.info(f"Starting SRA controller for a duration of {duration_s} seconds.")
        self.is_running = True
        start_time = time.time()
        end_time = start_time + duration_s

        # Initialize baseline stats
        initial_stats = self.hal.get_line_stats()
        self.last_crc_errors = initial_stats.get('crc_errors', 0) if initial_stats else 0
        self.last_check_time = start_time

        while self.is_running and time.time() < end_time:
            self._update_state()
            self._run_state_action()
            time.sleep(self.monitoring_interval_s)

        logging.info("SRA controller has finished its run.")
        self.is_running = False

    def stop(self):
        """Stops the SRA controller loop."""
        logging.info("Stopping SRA controller.")
        self.is_running = False