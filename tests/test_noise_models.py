import unittest
import numpy as np
from src.noise_models import ImpulseNoise, SHINE, AMRadioInterference, REIN

class TestNoiseModels(unittest.TestCase):
    def setUp(self):
        """Set up common resources for tests."""
        self.tones = np.linspace(138e3, 17e6, 4096)
        self.symbol_rate = 4312.5
        self.duration = 1.0

    def test_impulse_noise_generation(self):
        """Test that impulse noise generates a valid PSD."""
        impulse_model = ImpulseNoise(arrival_rate_per_sec=10)
        psd = impulse_model.generate_noise_psd(self.tones, self.symbol_rate, self.duration)
        self.assertEqual(psd.shape, self.tones.shape)
        self.assertTrue(np.all(psd < 0)) # PSD should be in dBm/Hz, so negative

    def test_shine_model(self):
        """Test the SHINE model combines stationary and impulse noise."""
        stationary_noise = np.full_like(self.tones, -140.0)
        impulse_model = ImpulseNoise(arrival_rate_per_sec=1)
        shine_model = SHINE(stationary_noise, impulse_model)

        psd = shine_model.generate_noise_psd(self.tones, self.symbol_rate, self.duration)
        self.assertEqual(psd.shape, self.tones.shape)
        # The combined noise should be higher than the stationary noise floor
        self.assertTrue(np.any(psd > -140.0))

    def test_am_radio_interference(self):
        """Test the AM radio interference model."""
        stations = [
            {'frequency_hz': 650e3, 'power_dbm': -50, 'bandwidth_hz': 10e3},
            {'frequency_hz': 1200e3, 'power_dbm': -60, 'bandwidth_hz': 10e3}
        ]
        am_model = AMRadioInterference(stations)
        psd = am_model.generate_noise_psd(self.tones)
        self.assertEqual(psd.shape, self.tones.shape)

        # Check that there is interference around the station frequencies
        affected_mask_1 = (self.tones >= 645e3) & (self.tones <= 655e3)
        self.assertTrue(np.any(psd[affected_mask_1] > -200.0))

        # Check that areas with no stations have very low noise
        unaffected_mask = (self.tones > 1300e3)
        self.assertTrue(np.all(psd[unaffected_mask] == -200.0))

    def test_rein_model(self):
        """Test the REIN model generates harmonic noise."""
        # We use a higher, less realistic fundamental frequency to ensure the harmonics are sparse
        # enough to test the "peaky" nature of the noise, as the test tones are widely spaced.
        # With a low fundamental (e.g., 100 Hz), harmonics are denser than tones,
        # causing noise to appear on almost every tone.
        rein_model = REIN(frequency_hz=30e3, power_dbm=-70, bandwidth_hz=500)
        psd = rein_model.generate_noise_psd(self.tones)
        self.assertEqual(psd.shape, self.tones.shape)

        num_affected_tones = np.sum(psd > -200.0)

        # There should be distinct peaks, so not all values will be the noise floor
        self.assertTrue(num_affected_tones > 0)

        # The number of affected tones should be limited and far less than the total number of tones
        self.assertTrue(num_affected_tones < len(self.tones) / 2)

if __name__ == '__main__':
    unittest.main()