"""
This module provides the CrosstalkSimulator class, which is responsible for
generating realistic crosstalk noise profiles based on physical models.

Crosstalk is a major limiting factor in DSL performance, and by simulating it,
we can develop and test mitigation strategies in a controlled manner.
"""
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CrosstalkSimulator:
    """
    Generates simulated FEXT (Far-End Crosstalk) and NEXT (Near-End Crosstalk)
    noise profiles for DSL lines.
    """

    def __init__(self, num_tones: int = 4096, aggressor_count: int = 1):
        """
        Initializes the simulator.

        Args:
            num_tones (int): The number of tones in the DSL signal (e.g., 4096 for VDSL2).
            aggressor_count (int): The number of interfering lines to simulate.
        """
        self.num_tones = num_tones
        self.aggressor_count = aggressor_count
        # A simplified crosstalk coupling constant. In reality, this is frequency-dependent.
        self.fext_coupling_k = 9e-20

    def _calculate_psd(self, tone_index: int) -> float:
        """
        Calculates a simplified Power Spectral Density (PSD) for a given tone.
        This model assumes a constant -40 dBm/Hz, which is a common value for VDSL2.
        """
        # A more complex model would vary this based on the VDSL2 band plan.
        return 1e-7  # Corresponds to -40 dBm/Hz

    def generate_fext_profile(self, custom_aggressor_psd: np.ndarray = None) -> np.ndarray:
        """
        Generates a Far-End Crosstalk (FEXT) noise profile.

        FEXT is the noise induced on a victim line by signals traveling in the
        same direction on aggressor lines. It increases with frequency.

        Args:
            custom_aggressor_psd (np.ndarray, optional): A custom PSD for aggressor lines.
                                                         If None, a default is calculated.

        Returns:
            np.ndarray: An array of FEXT noise values (in Watts/Hz) for each tone.
        """
        logging.info(f"Generating FEXT profile for {self.aggressor_count} aggressor(s)...")
        fext_profile = np.zeros(self.num_tones)
        tone_frequency_spacing = 4312.5  # Hz for VDSL2

        aggressor_psd = np.zeros(self.num_tones)
        if custom_aggressor_psd is not None and len(custom_aggressor_psd) == self.num_tones:
            aggressor_psd = custom_aggressor_psd
        else:
            for i in range(self.num_tones):
                aggressor_psd[i] = self._calculate_psd(i)

        for i in range(self.num_tones):
            frequency = (i + 1) * tone_frequency_spacing
            # FEXT model: FEXT = N * k * (f^2) * |H(f)|^2 * PSD_aggressor
            # We simplify |H(f)|^2 (channel transfer function) to 1 for this simulation.
            fext_profile[i] = self.aggressor_count * self.fext_coupling_k * (frequency ** 2) * aggressor_psd[i]

        return fext_profile

    def generate_next_profile(self) -> np.ndarray:
        """
        Generates a Near-End Crosstalk (NEXT) noise profile.

        NEXT is noise from signals traveling in the opposite direction. It is
        generally much stronger than FEXT but is less of an issue in modern DSL
        systems due to frequency division duplexing (FDD). This is included
        for completeness.

        Returns:
            np.ndarray: An array of NEXT noise values (in Watts/Hz) for each tone.
        """
        logging.info(f"Generating NEXT profile for {self.aggressor_count} aggressor(s)...")
        # NEXT is often modeled as relatively flat across frequencies in simplified models.
        # We will use a constant value for this simulation.
        next_power = 1e-11 # A constant -80 dBm/Hz noise floor
        next_profile = np.full(self.num_tones, next_power * self.aggressor_count)
        return next_profile

    def combine_noise_sources(self, fext_profile: np.ndarray, next_profile: np.ndarray) -> np.ndarray:
        """
        Combines different noise profiles into a single total noise profile.

        Args:
            fext_profile (np.ndarray): The FEXT noise profile.
            next_profile (np.ndarray): The NEXT noise profile.

        Returns:
            np.ndarray: The total combined noise profile.
        """
        # Incoherent noise sources add together.
        return fext_profile + next_profile