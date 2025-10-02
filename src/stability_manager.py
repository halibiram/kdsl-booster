import logging
from typing import TYPE_CHECKING
from src.keenetic_dsl_interface import DslHalBase
from src.enums import LineQuality

if TYPE_CHECKING:
    from src.sra_controller import SRAController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StabilityManager:
    """
    Manages the logic for stabilizing a DSL line based on its quality and
    pre-defined conservative profiles.
    """
    def __init__(self, hal: DslHalBase, controller: 'SRAController'):
        """
        Initializes the StabilityManager.

        Args:
            hal: An instance of a DSL Hardware Abstraction Layer (HAL).
            controller: The SRAController instance to access its state.
        """
        self.hal = hal
        self.controller = controller

    def apply_conservative_profile(self):
        """Applies a conservative parameter set based on the current line quality."""
        line_quality = self.controller.line_quality
        if line_quality not in self.controller.conservative_profiles:
            return

        profile = self.controller.conservative_profiles[line_quality]
        logging.warning(f"Line quality is {line_quality.value}. Applying conservative profile: {profile}")

        # Apply SNR margin target
        if 'snr_margin_target_db' in profile:
            target_snr_db = profile['snr_margin_target_db']
            self.hal.set_snr_margin(int(target_snr_db * 10))

        # Apply latency profile
        if 'latency_profile' in profile and self.controller.current_latency_profile != profile['latency_profile']:
            self.hal.set_latency_profile(profile['latency_profile'])
            self.controller.current_latency_profile = profile['latency_profile']

        # Apply Impulse Noise Protection (INP)
        if 'inp' in profile:
            try:
                self.hal.set_inp(profile['inp'])
            except NotImplementedError:
                logging.warning("INP setting is not supported by the current HAL.")

    def stabilize_line(self):
        """
        Action taken when the line is unstable. The primary goal is to
        apply a conservative profile to regain stability. If no specific
        profile is defined for the current quality, it falls back to
        incrementally increasing the SNR margin.
        """
        line_quality = self.controller.line_quality
        conservative_profiles = self.controller.conservative_profiles

        if line_quality in conservative_profiles:
            self.apply_conservative_profile()
        else:
            # Fallback for general instability
            current_snr = self.hal.get_snr_margin()
            if current_snr is not None:
                target_snr = current_snr + self.controller.snr_increase_step_db
                logging.info(f"Stabilizing line: Incrementally increasing SNR margin to {target_snr:.1f} dB.")
                self.hal.set_snr_margin(int(target_snr * 10))