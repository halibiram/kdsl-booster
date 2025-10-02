import time
import logging
from src.keenetic_dsl_interface import DslHalBase
from src.line_diagnostics import LineDiagnostics
from src.stability_manager import StabilityManager
from src.enums import SRAState, LineQuality

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SRAController:
    """
    Manages Seamless Rate Adaptation (SRA) and adaptive latency by monitoring
    line conditions and making intelligent adjustments to maintain an optimal balance
    between performance, stability, and power consumption.
    """

    def __init__(self, hal: DslHalBase, traffic_monitor=None, diagnostics: LineDiagnostics = None):
        """
        Initializes the SRA Controller.

        Args:
            hal: An instance of a DslHalBase implementation for hardware interaction.
            traffic_monitor: An optional utility to monitor network traffic volume.
            diagnostics: An optional instance of LineDiagnostics for deeper line analysis.
        """
        self.hal = hal
        self.traffic_monitor = traffic_monitor
        self.diagnostics = diagnostics if diagnostics else LineDiagnostics(hal)
        self.stability_manager = StabilityManager(hal, self)
        self.state = SRAState.STABLE
        self.line_quality = LineQuality.GOOD  # Start with a reasonable default
        self.is_running = False
        self.last_crc_errors = 0
        self.stable_since_time = time.time()
        self.last_check_time = time.time()
        self.current_power_boost_db = 0
        self.current_latency_profile = 'stable'  # Start with a safe default
        self.last_stable_config = {}
        self.disconnect_events = 0

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

        # --- Adaptive Latency Parameters ---
        self.latency_check_interval_s = 30 # How often to re-evaluate latency profile
        self.crc_threshold_for_stable_latency = 5 # If new errors exceed this, switch to 'stable' profile
        self.crc_threshold_for_fast_latency = 0 # New errors must be below this to switch to 'fast'

        # --- Conservative Profile Definitions ---
        self.conservative_profiles = {
            LineQuality.POOR: {
                'snr_margin_target_db': 9,  # Target a higher, more stable SNR margin
                'latency_profile': 'stable',
                'inp': 2,  # Increase Impulse Noise Protection
            },
            LineQuality.VERY_POOR: {
                'snr_margin_target_db': 12, # Target a very high SNR margin
                'latency_profile': 'stable',
                'inp': 4,  # Maximize Impulse Noise Protection
            }
        }

    def _save_stable_config(self):
        """Saves the last known good configuration of the line."""
        current_snr = self.hal.get_snr_margin()
        if current_snr is not None:
            self.last_stable_config = {
                'snr_margin': int(current_snr * 10),
                'latency_profile': self.current_latency_profile,
                'power_boost_db': self.current_power_boost_db,
            }
            logging.info(f"Saved stable configuration: {self.last_stable_config}")

    def _revert_to_stable_config(self):
        """Reverts the line settings to the last known good configuration."""
        if not self.last_stable_config:
            logging.warning("No stable configuration saved. Cannot revert.")
            return

        logging.warning(f"Reverting to last known stable configuration: {self.last_stable_config}")
        config = self.last_stable_config
        self.hal.set_snr_margin(config['snr_margin'])
        self.hal.set_latency_profile(config['latency_profile'])
        self.hal.set_upstream_power_boost(config['power_boost_db'])
        # Reset state to allow for re-stabilization
        self.state = SRAState.STABLE
        self.stable_since_time = time.time()

    def _check_for_disconnect(self) -> bool:
        """
        Checks if the line has disconnected and triggers a revert if so.
        Returns:
            True if the line is disconnected, False otherwise.
        """
        link_status = self.hal.get_link_status()
        if link_status.lower() not in ['up', 'showtime']:
            logging.error(f"Link is down! (Status: {link_status}). Reverting to last stable config.")
            self.disconnect_events += 1
            self._revert_to_stable_config()
            # Give the line time to recover before the next check
            time.sleep(self.monitoring_interval_s * 2)
            return True
        return False

    def _assess_line_quality(self, new_errors: int) -> LineQuality:
        """
        Assesses the current line quality based on CRC errors and diagnostic data.

        Args:
            new_errors: The number of new CRC errors since the last check.

        Returns:
            The assessed LineQuality.
        """
        # --- CRC-based Assessment ---
        if new_errors > self.crc_error_threshold * 2:
            logging.warning("Line quality is VERY_POOR due to high CRC errors.")
            return LineQuality.VERY_POOR
        if new_errors > self.crc_error_threshold:
            logging.warning("Line quality is POOR due to moderate CRC errors.")
            return LineQuality.POOR

        # --- Diagnostic-based Assessment (if available) ---
        if self.diagnostics:
            qln_analysis = self.diagnostics.analyze_qln()
            hlog_analysis = self.diagnostics.analyze_hlog()

            qln_anomalies = qln_analysis.get("anomalous_tones_found", 0)
            hlog_deviations = hlog_analysis.get("deviating_tones_found", 0)

            if qln_anomalies > 50 or hlog_deviations > 100:
                logging.warning("Line quality is POOR due to high QLN/Hlog anomalies.")
                return LineQuality.POOR
            if qln_anomalies > 10 or hlog_deviations > 20:
                logging.info("Line quality is GOOD, with some QLN/Hlog anomalies.")
                return LineQuality.GOOD

        # --- Default Assessment ---
        if new_errors == 0:
            return LineQuality.EXCELLENT
        else:
            return LineQuality.GOOD

    def _update_state_and_latency(self):
        """
        Analyzes line statistics and traffic to determine the current state of the line
        and the optimal latency profile.
        """
        current_stats = self.hal.get_line_stats()
        if not current_stats:
            logging.warning("Could not retrieve line stats. Assuming UNSTABLE.")
            self.state = SRAState.UNSTABLE
            self.line_quality = LineQuality.VERY_POOR
            self._update_latency_profile(is_unstable=True)
            return

        current_crc_errors = current_stats.get('crc_errors', 0)
        new_errors = current_crc_errors - self.last_crc_errors

        # Assess line quality based on new errors and other diagnostics
        self.line_quality = self._assess_line_quality(new_errors)

        if self.line_quality in [LineQuality.POOR, LineQuality.VERY_POOR]:
            logging.warning(f"Line has become unstable with quality '{self.line_quality.value}' and {new_errors} new CRC errors.")
            self.state = SRAState.UNSTABLE
            self.stable_since_time = time.time()  # Reset stable timer
            self._update_latency_profile(is_unstable=True)
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
                    self.state = SRAState.STABLE  # Stable but no need to change rate
            else:
                self.state = SRAState.STABLE

            # Now, check if we should change the latency profile
            self._update_latency_profile(new_errors=new_errors)

        self.last_crc_errors = current_crc_errors

    def _update_latency_profile(self, new_errors: int = 0, is_unstable: bool = False):
        """Decides and applies the optimal latency profile based on line conditions."""
        new_profile = self.current_latency_profile

        if is_unstable or new_errors > self.crc_threshold_for_stable_latency:
            if self.current_latency_profile != 'stable':
                logging.warning(f"High CRC count ({new_errors}). Switching to 'stable' latency profile for safety.")
                new_profile = 'stable'
        else:
            time_stable = time.time() - self.stable_since_time
            if time_stable > self.stable_time_for_optimization_s and new_errors <= self.crc_threshold_for_fast_latency:
                # Placeholder for more advanced logic to choose between 'fast' and 'gaming'
                # For now, we prefer 'fast' as a general optimization.
                if self.current_latency_profile != 'fast':
                    logging.info(f"Line is very stable (new errors: {new_errors}). Switching to 'fast' latency profile.")
                    new_profile = 'fast'

        if new_profile != self.current_latency_profile:
            success = self.hal.set_latency_profile(new_profile)
            if success:
                self.current_latency_profile = new_profile
            else:
                logging.error(f"Failed to switch latency profile to '{new_profile}'. Reverting to previous state.")

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
            self._save_stable_config()  # Save config before attempting a risky optimization
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
        Action taken when the line is unstable. Delegates the stabilization
        logic to the StabilityManager.
        """
        self.stability_manager.stabilize_line()

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
        # Set initial latency profile and save it as the first stable config
        self.hal.set_latency_profile(self.current_latency_profile)
        self._save_stable_config()

        while self.is_running and time.time() < end_time:
            # Check for disconnects first
            if self._check_for_disconnect():
                continue  # Skip the rest of the loop to allow recovery

            self._update_state_and_latency()
            self._run_state_action()
            time.sleep(self.monitoring_interval_s)

        logging.info(f"SRA controller has finished its run. Total disconnect events: {self.disconnect_events}")
        self.is_running = False

    def stop(self):
        """Stops the SRA controller loop."""
        logging.info("Stopping SRA controller.")
        self.is_running = False