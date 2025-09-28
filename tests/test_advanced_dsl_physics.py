import pytest
import numpy as np
from src.advanced_dsl_physics import AdvancedDSLPhysics, VDSL2_PROFILES

@pytest.fixture
def physics_model_17a():
    """Provides a default AdvancedDSLPhysics instance for the 17a profile."""
    return AdvancedDSLPhysics(profile='17a')

def test_invalid_profile_raises_error():
    """Tests that initializing with an unsupported profile raises a ValueError."""
    with pytest.raises(ValueError):
        AdvancedDSLPhysics(profile='invalid_profile')

def test_tone_generation(physics_model_17a):
    """
    Tests that the tone frequencies are generated correctly for the profile.
    """
    profile_data = VDSL2_PROFILES['17a']
    tone_spacing = profile_data['tone_spacing_hz']

    # Check if the number of tones is reasonable
    assert len(physics_model_17a.tones) > 2500  # Corrected expectation
    assert len(physics_model_17a.tones) < profile_data['total_tones']

    # Check if the first and last tones are within the expected frequency bands
    first_band_start, _ = profile_data['frequency_bands'][0]
    _, last_band_end = profile_data['frequency_bands'][-1]

    assert physics_model_17a.tones[0] >= first_band_start
    assert physics_model_17a.tones[-1] <= last_band_end

    # Check that tone frequencies are increasing
    assert np.all(np.diff(physics_model_17a.tones) > 0)

def test_attenuation_increases_with_distance_and_frequency(physics_model_17a):
    """
    Tests that the attenuation model correctly shows increased loss with
    higher distance and higher frequency.
    """
    attenuation_300m = physics_model_17a.model_attenuation_per_tone(distance_m=300)
    attenuation_800m = physics_model_17a.model_attenuation_per_tone(distance_m=800)

    # Attenuation at 800m should be greater than at 300m for all tones
    assert np.all(attenuation_800m > attenuation_300m)

    # Attenuation for the last tone (higher freq) should be greater than the first tone (lower freq)
    assert attenuation_300m[-1] > attenuation_300m[0]

def test_attenuation_increases_with_temperature(physics_model_17a):
    """
    Tests that attenuation increases when temperature is higher than the baseline 20C.
    """
    attenuation_20c = physics_model_17a.model_attenuation_per_tone(distance_m=500, temperature_c=20.0)
    attenuation_35c = physics_model_17a.model_attenuation_per_tone(distance_m=500, temperature_c=35.0)

    assert np.all(attenuation_35c > attenuation_20c)

def test_snr_decreases_with_distance_and_frequency(physics_model_17a):
    """
    Tests that the calculated SNR per tone decreases with distance and frequency,
    as expected due to attenuation.
    """
    snr_300m = physics_model_17a.calculate_snr_per_tone(distance_m=300)
    snr_800m = physics_model_17a.calculate_snr_per_tone(distance_m=800)

    # SNR at 800m should be lower than at 300m for all tones
    assert np.all(snr_800m < snr_300m)

    # SNR for the last tone (higher freq) should be lower than the first tone
    assert snr_300m[-1] < snr_300m[0]

def test_calculate_max_bitrate_realism(physics_model_17a):
    """
    Tests the max bitrate calculation for realistic scenarios with the tuned model.
    """
    # Short distance (300m) should yield a high bitrate
    rate_300m = physics_model_17a.calculate_max_bitrate(distance_m=300)
    assert 120 < rate_300m < 140  # Expect ~131 Mbps

    # Medium distance (700m) should yield a significantly lower but still usable rate
    rate_700m = physics_model_17a.calculate_max_bitrate(distance_m=700)
    assert 30 < rate_700m < 40 # Expect ~35 Mbps

    # Long distance (1500m) should result in a low bitrate
    rate_1500m = physics_model_17a.calculate_max_bitrate(distance_m=1500)
    assert 5 < rate_1500m < 10 # Expect ~6-7 Mbps

    # Very long distance should result in a practically zero bitrate
    rate_3000m = physics_model_17a.calculate_max_bitrate(distance_m=3000)
    assert rate_3000m < 1.0 # The model might calculate a negligible rate, which is acceptable

def test_bitrate_decreases_with_temperature(physics_model_17a):
    """
    Tests that the final bitrate is lower at higher temperatures due to increased attenuation.
    """
    rate_20c = physics_model_17a.calculate_max_bitrate(distance_m=500, temperature_c=20.0)
    rate_35c = physics_model_17a.calculate_max_bitrate(distance_m=500, temperature_c=35.0)

    assert rate_35c < rate_20c
    assert rate_35c > 0 # Should still be a viable connection